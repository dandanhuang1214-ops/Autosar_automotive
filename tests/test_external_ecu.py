from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from automotive_workbench.can_io import sha256_file
from automotive_workbench.external_ecu import (
    channel_lock,
    load_execution,
    read_json,
    run_external_ecu,
    stop_process,
    verify_external_ecu,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(root: Path, code: str = "import time; time.sleep(60)") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    executable = root / "ecu"
    executable.write_text(f"#!{sys.executable}\n{code}\n")
    executable.chmod(0o700)
    evidence = root / "evidence.txt"
    evidence.write_text("synthetic process fixture; no ECU build or CAN evidence\n")
    profile = read_json(ROOT / "examples/openbsw/read_cf01.json")
    profile["timeout_s"] = 0.05
    write_json(root / "profile.json", profile)
    roles = (
        "executable",
        "cache",
        "can_source",
        "docan_source",
        "uds_source",
        "configure_log",
        "build_log",
    )
    write_json(
        root / "build.json",
        {
            "schema_version": "external-ecu-build-0.1",
            "source_commit": "0" * 40,
            "preset": "synthetic-test",
            "configuration": "test-only",
            "bindings": {
                "channel": "p23-missing",
                **{
                    key: profile[key]
                    for key in ("request_id", "response_id", "did", "expected_data_hex")
                },
            },
            "commands": [["synthetic-fixture"]],
            "tools": {key: "test-only" for key in ("cmake", "compiler", "ninja")},
            "files": [
                {
                    "role": role,
                    "path": str(
                        (executable if role == "executable" else evidence).resolve()
                    ),
                    "sha256": sha256_file(
                        executable if role == "executable" else evidence
                    ),
                }
                for role in roles
            ],
        },
    )
    path = root / "execution.json"
    write_json(
        path,
        {
            "schema_version": "external-ecu-execution-0.1",
            "build": "build.json",
            "profile": "profile.json",
            "channel": "p23-missing",
            "startup_delay_s": 0.3,
            "shutdown_timeout_s": 0.05,
            "launch_ecu": True,
            "fault": "none",
        },
    )
    return path


class ExternalEcuTests(unittest.TestCase):
    def setUp(self):
        # Test locks never contend with an operator's live SocketCAN session.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        environment = patch.dict(os.environ, {"XDG_RUNTIME_DIR": directory.name})
        environment.start()
        self.addCleanup(environment.stop)

    def test_blocked_schema_and_portable_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixture(root / "source")
            for name in ("execution", "build"):
                Draft202012Validator(
                    read_json(ROOT / f"schemas/external-ecu-{name}.schema.json")
                ).validate(read_json(path.parent / (name + ".json")))
            result = run_external_ecu(path, root / "run")
            self.assertEqual(result["status"], "blocked")
            self.assertIsNone(result["ecu_pid"])
            Draft202012Validator(
                read_json(ROOT / "schemas/external-ecu-run.schema.json")
            ).validate(result)
            (root / "run").rename(root / "moved")
            # Original build and profile disappear: verification is snapshot-only.
            for source in path.parent.iterdir():
                source.unlink()
            report = root / "moved/external-ecu-report.json"
            self.assertEqual(verify_external_ecu(report)["status"], "passed")
            (root / "moved/inputs/profile.json").write_text("{}")
            with self.assertRaises(ValueError):
                verify_external_ecu(report)

    def test_preflight_rejects_before_output_or_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixture(root / "source")
            original = read_json(path)
            for mutation in (
                {"startup_delay_s": True},
                {"shutdown_timeout_s": float("nan")},
                {"channel": "../bad"},
                {"launch_ecu": 1},
                {"fault": []},
                {"extra": 1},
                {"schema_version": []},
            ):
                write_json(path, {**original, **mutation})
                with (
                    self.subTest(mutation=mutation),
                    patch("subprocess.Popen") as spawn,
                    self.assertRaises(ValueError),
                ):
                    run_external_ecu(path, root / "out")
                spawn.assert_not_called()
                self.assertFalse((root / "out").exists())
            write_json(path, original)
            (path.parent / "ecu").write_text("changed executable")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                run_external_ecu(path, root / "out")
            self.assertFalse((root / "out").exists())

    def test_missing_binary_is_blocked_and_fault_requires_declaration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixture(root / "source")
            profile = read_json(path.parent / "profile.json")
            profile["response_id"] += 1
            write_json(path.parent / "profile.json", profile)
            with self.assertRaisesRegex(ValueError, "binding mismatch"):
                load_execution(path)
            write_json(path, {**read_json(path), "fault": "wrong-response-id"})
            load_execution(path)
            (path.parent / "ecu").unlink()
            result = run_external_ecu(path, root / "out")
            self.assertEqual(
                (result["status"], result["reason"]),
                ("blocked", "missing_build_files:executable"),
            )

    def test_duplicate_json_and_build_roles_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixture(Path(tmp))
            path.write_text('{"schema_version": 1, "schema_version": 2}')
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_execution(path)
            path = fixture(Path(tmp))
            build = read_json(path.parent / "build.json")
            build["files"][1] = build["files"][0]
            write_json(path.parent / "build.json", build)
            with self.assertRaises(ValueError):
                load_execution(path)

    def test_report_tamper_and_output_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixture(root / "source")
            result = run_external_ecu(path, root / "out")
            with self.assertRaises(ValueError):
                run_external_ecu(path, root / "out")
            result["status"] = "passed"
            report = root / "out/external-ecu-report.json"
            write_json(report, result)
            with self.assertRaises(ValueError):
                verify_external_ecu(report)
            result["status"] = "blocked"
            result["inventory"][0]["path"] = "../escape"
            write_json(report, result)
            with self.assertRaises(ValueError):
                verify_external_ecu(report)

    def test_saved_source_binding_and_unexpected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = fixture(root / "source")
            result = run_external_ecu(path, root / "out")
            source = root / "out/inputs/can_source.txt"
            source.write_text("changed build evidence")
            for item in result["inventory"]:
                if item["path"] == "inputs/can_source.txt":
                    item["sha256"] = sha256_file(source)
            report = root / "out/external-ecu-report.json"
            write_json(report, result)
            with self.assertRaisesRegex(ValueError, "build source binding"):
                verify_external_ecu(report)
            (root / "out/unexpected.txt").write_text("extra")
            with self.assertRaisesRegex(ValueError, "inventory incomplete"):
                verify_external_ecu(report)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process contract")
    def test_partial_client_start_failure_still_reaps_ecu(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixture(Path(tmp) / "source")
            real_spawn = subprocess.Popen

            def spawn(command, **kwargs):
                if "read-uds-did" in command:
                    raise OSError("injected client spawn failure")
                return real_spawn(command, **kwargs)

            with (
                patch(
                    "automotive_workbench.external_ecu.probe_uds_backend",
                    return_value={"status": "available"},
                ),
                patch(
                    "automotive_workbench.external_ecu.subprocess.Popen",
                    side_effect=spawn,
                ),
            ):
                result = run_external_ecu(path, Path(tmp) / "out")
            self.assertEqual(result["reason"], "execution_error:OSError")
            self.assertIsNone(result["client_pid"])
            self.assertTrue(result["cleanup"]["ecu"]["reaped"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process contract")
    def test_real_sigterm_to_supervisor_cleans_owned_process(self):
        import time

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / "ready"
            path = fixture(
                root / "source",
                f"from pathlib import Path; import time; Path({str(marker)!r}).write_text('ready'); time.sleep(60)",
            )
            output = root / "out"
            worker = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; import automotive_workbench.external_ecu as e; e.probe_uds_backend=lambda c: {'status':'available'}; e.run_external_ecu(Path("
                    + repr(str(path))
                    + "),Path("
                    + repr(str(output))
                    + "))",
                ]
            )
            try:
                deadline = time.monotonic() + 5
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(marker.exists())
                worker.send_signal(signal.SIGTERM)
                self.assertEqual(worker.wait(timeout=5), 0)
                result = read_json(output / "external-ecu-report.json")
                self.assertEqual(result["reason"], "interrupted")
                self.assertTrue(result["cleanup"]["ecu"]["reaped"])
                with self.assertRaises(ProcessLookupError):
                    os.kill(result["ecu_pid"], 0)
            finally:
                if worker.poll() is None:
                    worker.terminate()
                    worker.wait(timeout=5)

    @unittest.skipUnless(
        sys.platform.startswith("linux"), "Linux process/lock contract"
    )
    def test_same_channel_lock_and_different_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixture(Path(tmp) / "source")
            with channel_lock("p23-missing"):
                with channel_lock("p23-other"):
                    pass
                result = run_external_ecu(path, Path(tmp) / "out")
            self.assertEqual(result["reason"], "channel_lock_busy")
            self.assertIsNone(result["ecu_pid"])
            with channel_lock("p23-missing"):
                pass

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process contract")
    def test_early_exit_and_client_failure_cleanup(self):
        for code, expected in (
            ("raise SystemExit(7)", "ecu_early_exit"),
            ("import time; time.sleep(60)", "client_report_missing"),
        ):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                path = fixture(Path(tmp) / "source", code)
                real_spawn = subprocess.Popen

                def spawn(command, **kwargs):
                    if "read-uds-did" in command:
                        command = [sys.executable, "-c", "raise SystemExit(9)"]
                    return real_spawn(command, **kwargs)

                with (
                    patch(
                        "automotive_workbench.external_ecu.probe_uds_backend",
                        return_value={"status": "available"},
                    ),
                    patch(
                        "automotive_workbench.external_ecu.subprocess.Popen",
                        side_effect=spawn,
                    ),
                ):
                    result = run_external_ecu(path, Path(tmp) / "out")
                self.assertEqual(result["reason"], expected)
                self.assertTrue(result["cleanup"]["ecu"]["reaped"])
                with self.assertRaises(ProcessLookupError):
                    os.kill(result["ecu_pid"], 0)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process contract")
    def test_client_deadline_cleans_both_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixture(Path(tmp) / "source")
            real_spawn = subprocess.Popen

            def spawn(command, **kwargs):
                if "read-uds-did" in command:
                    command = [sys.executable, "-c", "import time; time.sleep(60)"]
                return real_spawn(command, **kwargs)

            with (
                patch(
                    "automotive_workbench.external_ecu.probe_uds_backend",
                    return_value={"status": "available"},
                ),
                patch(
                    "automotive_workbench.external_ecu.subprocess.Popen",
                    side_effect=spawn,
                ),
            ):
                result = run_external_ecu(path, Path(tmp) / "out")
            self.assertEqual(result["reason"], "client_deadline")
            self.assertEqual(set(result["cleanup"]), {"client", "ecu"})
            self.assertTrue(all(item["reaped"] for item in result["cleanup"].values()))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process contract")
    def test_interrupt_cleanup_and_kill_escalation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fixture(Path(tmp) / "source")
            import time

            real_sleep = time.sleep
            interrupted = False

            def interrupt_once(delay):
                nonlocal interrupted
                if not interrupted:
                    interrupted = True
                    raise InterruptedError
                real_sleep(delay)

            with (
                patch(
                    "automotive_workbench.external_ecu.probe_uds_backend",
                    return_value={"status": "available"},
                ),
                patch(
                    "automotive_workbench.external_ecu.time.sleep",
                    side_effect=interrupt_once,
                ),
            ):
                result = run_external_ecu(path, Path(tmp) / "out")
            self.assertEqual(result["reason"], "interrupted")
            self.assertTrue(result["cleanup"]["ecu"]["reaped"])
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready',flush=True); time.sleep(60)",
                ],
                stdout=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                self.assertEqual(process.stdout.readline(), b"ready\n")
                cleanup = stop_process(process, 0.05)
                self.assertTrue(cleanup["kill_sent"])
                self.assertTrue(cleanup["reaped"])
                self.assertEqual(cleanup["returncode"], -signal.SIGKILL)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()


if __name__ == "__main__":
    unittest.main()

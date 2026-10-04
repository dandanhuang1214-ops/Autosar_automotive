"""Bounded Linux process orchestration for a separately built, external ECU.

Build provenance is caller-supplied evidence, not an ECU identity attestation.
The diagnostic client runs in its own process and never starts a responder.
"""

from __future__ import annotations

import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from automotive_workbench.can_io import BusConfig, sha256_file
from automotive_workbench.uds_client import load_did_profile
from automotive_workbench.uds_runtime import probe_uds_backend


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON member: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def _closed(value: Any, keys: str) -> None:
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise ValueError(f"Expected closed fields: {keys}")


def _string(value: Any) -> None:
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError("Expected non-empty string without NUL")


def _hash(value: Any) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected SHA-256")


def _time(value: Any, minimum: float, maximum: float) -> None:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError("Invalid bounded duration")


def _validate_documents(spec: dict, build: dict, profile: dict) -> None:
    _closed(
        spec,
        "schema_version build profile channel startup_delay_s shutdown_timeout_s launch_ecu fault",
    )
    if spec["schema_version"] != "external-ecu-execution-0.1":
        raise ValueError("Unsupported external execution version")
    for key in ("build", "profile", "channel"):
        _string(spec[key])
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", spec["channel"]):
        raise ValueError("Channel must be a Linux interface name")
    if not isinstance(spec["fault"], str) or spec["fault"] not in {
        "none",
        "wrong-did",
        "wrong-response-id",
    }:
        raise ValueError("Unknown explicit fault variant")
    if type(spec["launch_ecu"]) is not bool:
        raise ValueError("launch_ecu must be boolean")
    _time(spec["startup_delay_s"], 0.05, 10)
    _time(spec["shutdown_timeout_s"], 0.05, 5)
    _closed(
        build,
        "schema_version source_commit preset configuration bindings commands tools files",
    )
    if build["schema_version"] != "external-ecu-build-0.1":
        raise ValueError("Unsupported build version")
    if not isinstance(build["source_commit"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", build["source_commit"]
    ):
        raise ValueError("Build requires fixed source commit")
    for key in ("preset", "configuration"):
        _string(build[key])
    _closed(build["bindings"], "channel request_id response_id did expected_data_hex")
    for key, maximum in (("request_id", 2047), ("response_id", 2047), ("did", 65535)):
        if (
            type(build["bindings"][key]) is not int
            or not 0 <= build["bindings"][key] <= maximum
        ):
            raise ValueError("Invalid build addressing")
    if build["bindings"]["request_id"] == build["bindings"]["response_id"]:
        raise ValueError("Build request and response IDs must differ")
    # The profile validator also validates integer/range/data encodings here.
    fault_key = {"wrong-did": "did", "wrong-response-id": "response_id"}.get(
        spec["fault"]
    )
    for key, value in build["bindings"].items():
        actual = spec["channel"] if key == "channel" else profile[key]
        if type(value) is not type(actual) or (value != actual) != (key == fault_key):
            raise ValueError(
                "Build and client channel/address/DID/data binding mismatch"
            )
    _closed(build["tools"], "cmake compiler ninja")
    for value in build["tools"].values():
        _string(value)
    if not isinstance(build["commands"], list) or not build["commands"]:
        raise ValueError("Build requires command evidence")
    for command in build["commands"]:
        if not isinstance(command, list) or not command:
            raise ValueError("Build commands must be argument arrays")
        for argument in command:
            _string(argument)
    if not isinstance(build["files"], list):
        raise ValueError("Build files must be a list")


def load_execution(path: Path) -> tuple[dict, dict, dict, dict[str, bytes], list[str]]:
    """Validate all configuration and present files before creating any output."""
    spec = read_json(path)
    for key in ("build", "profile"):
        _string(spec.get(key))
    build_path, profile_path = (path.parent / spec[key] for key in ("build", "profile"))
    build = read_json(build_path)
    profile = read_json(profile_path)
    load_did_profile(profile_path)
    _validate_documents(spec, build, profile)
    roles = {
        "executable",
        "cache",
        "can_source",
        "docan_source",
        "uds_source",
        "configure_log",
        "build_log",
    }
    if len(build["files"]) != len(roles):
        raise ValueError(
            "Build requires binary, configuration, source and command logs"
        )
    snapshots = {
        "execution.json": path.read_bytes(),
        "build.json": build_path.read_bytes(),
        "profile.json": profile_path.read_bytes(),
    }
    missing = []
    for entry in build["files"]:
        _closed(entry, "role path sha256")
        _string(entry["role"])
        if entry["role"] not in roles:
            raise ValueError("Duplicate or unknown build file role")
        roles.remove(entry["role"])
        _string(entry["path"])
        _hash(entry["sha256"])
        source = build_path.parent / entry["path"]
        if source.is_symlink():
            raise ValueError("Build file must not be a symlink")
        if not source.exists():
            missing.append(entry["role"])
            continue
        if not source.is_file():
            raise ValueError("Build file must be regular")
        if sha256_file(source) != entry["sha256"]:
            raise ValueError(f"Build file hash mismatch: {entry['role']}")
        if entry["role"] != "executable":
            snapshots[entry["role"] + ".txt"] = source.read_bytes()
    return spec, build, profile, snapshots, missing


@contextmanager
def channel_lock(channel: str) -> Iterator[str]:
    if sys.platform == "win32":
        raise RuntimeError("SocketCAN channel locks require Linux")
    import fcntl

    directory = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "automotive-workbench"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"socketcan-{channel}.lock"
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield str(path)
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


@contextmanager
def _interrupts() -> Iterator[None]:
    def interrupt(signum: int, frame: Any) -> None:
        raise InterruptedError(f"signal {signum}")

    previous = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, interrupt)
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def stop_process(process: subprocess.Popen, timeout: float) -> dict:
    """Kill only our new session; include descendants even after parent exits."""
    if sys.platform == "win32":
        raise RuntimeError("External ECU process groups require Linux")
    result = {
        "pid": process.pid,
        "returncode": None,
        "term_sent": False,
        "kill_sent": False,
        "reaped": False,
    }
    try:
        os.killpg(process.pid, signal.SIGTERM)
        result["term_sent"] = True
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    # A parent may exit while descendants ignore TERM: always finish the group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
        result["kill_sent"] = True
    except ProcessLookupError:
        pass
    try:
        result["returncode"] = process.wait(timeout=timeout)
        result["reaped"] = True
    except subprocess.TimeoutExpired:
        pass
    if process.stdin is not None:
        process.stdin.close()
    return result


def _execute(
    spec: dict,
    build: dict,
    build_path: Path,
    output: Path,
    result: dict,
    lock_path: str,
) -> None:
    executable = next(item for item in build["files"] if item["role"] == "executable")
    binary = (build_path.parent / executable["path"]).resolve()
    ecu = None
    client = None
    cleanup = result["cleanup"]
    with (
        (output / "ecu.log").open("wb") as ecu_log,
        (output / "client.log").open("wb") as client_log,
    ):
        try:
            if spec["launch_ecu"]:
                # Recheck under the channel lock immediately before process creation.
                if sha256_file(binary) != executable["sha256"]:
                    raise ValueError("Executable changed after preflight")
                ecu = subprocess.Popen(
                    [str(binary)],
                    stdin=subprocess.PIPE,
                    stdout=ecu_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                result["ecu_pid"] = ecu.pid
                deadline = time.monotonic() + spec["startup_delay_s"]
                while time.monotonic() < deadline:
                    if ecu.poll() is not None:
                        result.update(status="failed", reason="ecu_early_exit")
                        return
                    time.sleep(min(0.02, max(0, deadline - time.monotonic())))
            env = dict(os.environ, AUTOMOTIVE_WORKBENCH_CHANNEL_LOCK=lock_path)
            command = [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                "read-uds-did",
                str(output / "inputs/profile.json"),
                "--interface",
                "socketcan",
                "--channel",
                spec["channel"],
                "--output",
                str(output / "diagnostic"),
            ]
            if "execution_context" in result:
                command += [
                    "--execution-context",
                    str(output / "inputs/execution-context.json"),
                ]
            client = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=client_log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            result["client_pid"] = client.pid
            timeout = result["profile_timeout_s"] + 5
            try:
                code = client.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                result.update(status="failed", reason="client_deadline")
                return
            diagnostic_path = output / "diagnostic/uds-did-report.json"
            if not diagnostic_path.is_file():
                result.update(status="failed", reason="client_report_missing")
                return
            diagnostic = read_json(diagnostic_path)
            if code != {"passed": 0, "failed": 2, "blocked": 3}.get(
                diagnostic.get("status", "")
            ):
                result.update(status="failed", reason="client_exit_mismatch")
                return
            result.update(
                status=diagnostic["status"],
                reason=diagnostic["reason"],
                diagnostic="diagnostic/uds-did-report.json",
            )
            if ecu is not None and ecu.poll() is not None:
                result.update(status="failed", reason="ecu_exited_during_diagnostic")
        except InterruptedError:
            raise
        except (OSError, ValueError) as exc:
            result.update(
                status="failed", reason=f"execution_error:{type(exc).__name__}"
            )
        finally:
            for role, process in (("client", client), ("ecu", ecu)):
                if process is not None:
                    cleanup[role] = stop_process(process, spec["shutdown_timeout_s"])
            if any(not item["reaped"] for item in cleanup.values()):
                result.update(status="failed", reason="cleanup_failed")


def run_external_ecu(
    path: Path, output: Path, *, execution_context: dict | None = None
) -> dict:
    if execution_context is not None:
        validate_execution_context(execution_context)
    spec, build, profile, snapshots, missing = load_execution(path)
    if output.is_symlink() or (
        output.exists() and (not output.is_dir() or any(output.iterdir()))
    ):
        raise ValueError("External ECU output must be empty or absent")
    output = output.resolve()
    (output / "inputs").mkdir(parents=True)
    for name, data in snapshots.items():
        (output / "inputs" / name).write_bytes(data)
    result: dict[str, Any] = {
        "artifact_type": "external-ecu-run",
        "schema_version": "external-ecu-run-0.1",
        "status": "blocked",
        "reason": "",
        "channel": spec["channel"],
        "evidence_kind": "external-process-socketcan",
        "target_identity_verified": False,
        "source_commit": build["source_commit"],
        "launch_ecu": spec["launch_ecu"],
        "profile_timeout_s": profile["timeout_s"],
        "ecu_pid": None,
        "client_pid": None,
        "lock": "not_acquired",
        "cleanup": {},
        "diagnostic": None,
        "inventory": [],
    }
    if execution_context is not None:
        result.update(
            schema_version="external-ecu-run-0.2", execution_context=execution_context
        )
        write_json(output / "inputs/execution-context.json", execution_context)
    try:
        with _interrupts():
            if missing:
                result["reason"] = "missing_build_files:" + ",".join(missing)
            elif not sys.platform.startswith("linux"):
                result["reason"] = "linux_required"
            else:
                try:
                    with channel_lock(spec["channel"]) as lock:
                        result["lock"] = "held"
                        probe = probe_uds_backend(
                            BusConfig("socketcan", spec["channel"])
                        )
                        write_json(output / "probe.json", probe)
                        if probe["status"] != "available":
                            result["reason"] = "backend_unavailable:" + probe["reason"]
                        else:
                            _execute(
                                spec,
                                build,
                                path.parent / spec["build"],
                                output,
                                result,
                                lock,
                            )
                except BlockingIOError:
                    result["reason"] = "channel_lock_busy"
    except (InterruptedError, KeyboardInterrupt):
        result.update(status="failed", reason="interrupted")
    except OSError as exc:
        result.update(
            status="blocked", reason=f"environment_error:{type(exc).__name__}"
        )
    # Normalize only evidence source paths, leaving runtime observations unchanged.
    diagnostic_path = output / "diagnostic/uds-did-report.json"
    if diagnostic_path.exists():
        diagnostic = read_json(diagnostic_path)
        diagnostic["profile"]["source"] = "../inputs/profile.json"
        if diagnostic["capture"]:
            diagnostic["capture"]["source"] = "uds-did.log"
        diagnostic["source_artifacts"] = [diagnostic["profile"]] + (
            [diagnostic["capture"]] if diagnostic["capture"] else []
        )
        write_json(diagnostic_path, diagnostic)
    result["inventory"] = [
        {
            "path": str(item.relative_to(output)).replace(os.sep, "/"),
            "sha256": sha256_file(item),
        }
        for item in sorted(output.rglob("*"))
        if item.is_file()
    ]
    write_json(output / "external-ecu-report.json", result)
    return result


def verify_external_ecu(report_path: Path) -> dict:
    """Offline byte integrity and diagnostic binding; never execute saved inputs."""
    if report_path.is_symlink():
        raise ValueError("Report must not be a symlink")
    result = read_json(report_path)
    _closed(
        result,
        "artifact_type schema_version status reason channel evidence_kind target_identity_verified source_commit launch_ecu profile_timeout_s ecu_pid client_pid lock cleanup diagnostic inventory"
        + (
            " execution_context"
            if result.get("schema_version") == "external-ecu-run-0.2"
            else ""
        ),
    )
    if (
        result["artifact_type"] != "external-ecu-run"
        or result["evidence_kind"] != "external-process-socketcan"
        or result["target_identity_verified"] is not False
    ):
        raise ValueError("Invalid external evidence kind")
    if (
        not isinstance(result["status"], str)
        or result["status"] not in {"passed", "failed", "blocked"}
        or not isinstance(result["lock"], str)
        or result["lock"] not in {"held", "not_acquired"}
    ):
        raise ValueError("Invalid external ECU status")
    if result["schema_version"] not in ("external-ecu-run-0.1", "external-ecu-run-0.2"):
        raise ValueError("Unsupported external ECU report")
    if (
        not isinstance(result["reason"], str)
        or type(result["launch_ecu"]) is not bool
        or not isinstance(result["inventory"], list)
        or not isinstance(result["cleanup"], dict)
    ):
        raise ValueError("Malformed external ECU report fields")
    _time(result["profile_timeout_s"], 0.05, 30)
    for role in ("ecu", "client"):
        pid = result[role + "_pid"]
        if pid is not None and (type(pid) is not int or pid < 1):
            raise ValueError("Invalid process ID")
    if set(result["cleanup"]) - {"ecu", "client"}:
        raise ValueError("Unknown cleanup role")
    for item in result["cleanup"].values():
        _closed(item, "pid returncode term_sent kill_sent reaped")
        if (
            type(item["pid"]) is not int
            or item["pid"] < 1
            or (item["returncode"] is not None and type(item["returncode"]) is not int)
        ):
            raise ValueError("Invalid cleanup process result")
        if any(
            type(item[key]) is not bool for key in ("term_sent", "kill_sent", "reaped")
        ):
            raise ValueError("Invalid cleanup flags")
    root = report_path.parent.resolve()
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("Saved inventory must not contain symlinks")
    seen = set()
    for item in result["inventory"]:
        _closed(item, "path sha256")
        _hash(item["sha256"])
        relative = item["path"]
        if (
            not isinstance(relative, str)
            or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", relative)
            or any(token in {"", ".", ".."} for token in relative.split("/"))
            or relative.startswith("/")
            or relative in seen
        ):
            raise ValueError("Invalid inventory path")
        seen.add(relative)
        path = root / relative
        if (
            path.is_symlink()
            or root not in path.resolve().parents
            or not path.is_file()
            or sha256_file(path) != item["sha256"]
        ):
            raise ValueError("External ECU inventory mismatch")
    expected = {
        str(p.relative_to(root)).replace(os.sep, "/")
        for p in root.rglob("*")
        if p.is_file() and p != report_path.resolve()
    }
    if (
        expected != seen
        or not {"inputs/execution.json", "inputs/build.json", "inputs/profile.json"}
        <= seen
    ):
        raise ValueError("External ECU inventory incomplete")
    if result["schema_version"] == "external-ecu-run-0.2":
        validate_execution_context(result["execution_context"])
        if (
            read_json(root / "inputs/execution-context.json")
            != result["execution_context"]
        ):
            raise ValueError("External execution context differs from snapshot")
    spec, build, profile = (
        read_json(root / "inputs" / name)
        for name in ("execution.json", "build.json", "profile.json")
    )
    load_did_profile(root / "inputs/profile.json")
    _validate_documents(spec, build, profile)
    roles = set()
    for item in build["files"]:
        _closed(item, "role path sha256")
        if (
            item["role"]
            not in {
                "executable",
                "cache",
                "can_source",
                "docan_source",
                "uds_source",
                "configure_log",
                "build_log",
            }
            or item["role"] in roles
        ):
            raise ValueError("Invalid saved build role")
        roles.add(item["role"])
        _hash(item["sha256"])
        source = root / "inputs" / (item["role"] + ".txt")
        if (
            item["role"] != "executable"
            and source.exists()
            and sha256_file(source) != item["sha256"]
        ):
            raise ValueError("Saved build source binding mismatch")
        if (
            result["status"] != "blocked"
            and item["role"] != "executable"
            and not source.is_file()
        ):
            raise ValueError("Executed report missing build evidence")
    if len(roles) != 7:
        raise ValueError("Incomplete build roles")
    if (
        result["source_commit"] != build["source_commit"]
        or result["channel"] != spec["channel"]
        or result["launch_ecu"] != spec["launch_ecu"]
        or result["profile_timeout_s"] != profile["timeout_s"]
    ):
        raise ValueError("Report input binding mismatch")
    if result["diagnostic"] is not None:
        if (
            result["diagnostic"] != "diagnostic/uds-did-report.json"
            or result["diagnostic"] not in seen
        ):
            raise ValueError("Invalid diagnostic path")
        diagnostic = read_json(root / result["diagnostic"])
        if result["schema_version"] == "external-ecu-run-0.2":
            if (
                diagnostic.get("schema_version") != "uds-did-read-0.2"
                or diagnostic.get("execution_context") != result["execution_context"]
            ):
                raise ValueError("Diagnostic client execution context mismatch")
            if diagnostic.get("expected_data_hex") != profile["expected_data_hex"]:
                raise ValueError("Diagnostic client expected data drift")
            if diagnostic.get("status") == "passed" and (
                diagnostic.get("response_payload_hex")
                != f"62{profile['did']:04X}" + profile["expected_data_hex"]
                or diagnostic.get("actual_data_hex") != profile["expected_data_hex"]
                or diagnostic.get("reason") != ""
                or diagnostic.get("negative_response_code") is not None
            ):
                raise ValueError("Passed diagnostic payload mismatch")
        if (
            diagnostic["profile"]["sha256"] != sha256_file(root / "inputs/profile.json")
            or diagnostic["request_payload_hex"] != f"22{profile['did']:04X}"
            or diagnostic["bus_config"]
            != {
                "interface": "socketcan",
                "channel": spec["channel"],
                "receive_own_messages": False,
                "fd": False,
            }
        ):
            raise ValueError("Diagnostic profile or addressing mismatch")
        if diagnostic["capture"] and diagnostic["capture"]["sha256"] != sha256_file(
            root / "diagnostic/uds-did.log"
        ):
            raise ValueError("Diagnostic capture mismatch")
    if result["status"] == "passed":
        if (
            result["diagnostic"] != "diagnostic/uds-did-report.json"
            or result["lock"] != "held"
            or result["client_pid"] is None
        ):
            raise ValueError("Passed execution missing diagnostic/process evidence")
        if result["launch_ecu"] and result["ecu_pid"] is None:
            raise ValueError("Passed managed execution missing ECU process")
        diagnostic = read_json(root / result["diagnostic"])
        if (
            diagnostic["status"] != "passed"
            or diagnostic["profile"]["sha256"]
            != sha256_file(root / "inputs/profile.json")
            or diagnostic["actual_data_hex"] != profile["expected_data_hex"]
        ):
            raise ValueError("Passed execution diagnostic mismatch")
        for role in ["client", "ecu"] if result["launch_ecu"] else ["client"]:
            if (
                not result["cleanup"].get(role, {}).get("reaped")
                or result["cleanup"][role]["pid"] != result[role + "_pid"]
            ):
                raise ValueError("Passed execution missing process cleanup")
    return {
        "status": "passed",
        "verified_files": len(seen),
        "execution_status": result["status"],
        "scope": "saved-byte-integrity-and-bindings; no execution or ECU authentication",
    }


def validate_execution_context(value: Any) -> None:
    """Same-run binding, not an authentication or signing mechanism."""
    _closed(
        value,
        "run_id project_sha256 baseline_sha256 candidate_sha256 policy_sha256 execution_basis",
    )
    if not isinstance(value["run_id"], str) or not re.fullmatch(
        r"[a-f0-9]{32}", value["run_id"]
    ):
        raise ValueError("Invalid execution run ID")
    for key in value.keys() - {"run_id"}:
        _hash(value[key])

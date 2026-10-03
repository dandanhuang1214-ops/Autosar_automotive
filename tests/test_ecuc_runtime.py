from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from automotive_workbench.can_io import BusConfig
from automotive_workbench.ecuc_project import sha
from automotive_workbench.project_ecuc import verify
from automotive_workbench.project_workflow import run_project
from automotive_workbench.project_comparison import (
    compare_project_reports,
    validate_project_comparison,
)
from automotive_workbench.project_review import run_project_review

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class LinkedRuntimeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "inputs"
        shutil.copytree(ROOT / "examples/ecuc_runtime", self.source)
        self.path = self.source / "integration.project.json"
        self.project = read(self.path)
        shutil.copytree(self.source / "integration", self.source / "candidate")
        self.project["inputs"]["candidate"] = {
            k: [s.replace("integration/", "candidate/") for s in v]
            if isinstance(v, list)
            else v.replace("integration/", "candidate/")
            for k, v in self.project["inputs"]["candidate"].items()
        }

    def mutate(self, old, new):
        p = self.source / "candidate/modules.arxml"
        s = p.read_text()
        self.assertIn(old, s)
        p.write_text(s.replace(old, new, 1))

    def execute(self, name="run", config=None):
        self.path.write_text(json.dumps(self.project))
        result = run_project(
            self.path, self.root / name, config or BusConfig("virtual", "p29-tests")
        )
        path = Path(result["report_json"])
        for schema, data in [
            ("workbench-project", self.project),
            ("project-acceptance", read(path)),
            ("ecuc-project-acceptance", read(path.parent / "ecuc-stage.json")),
            ("ecuc-runtime-link", read(path.parent / "runtime-link.json")),
        ]:
            Draft202012Validator(read(ROOT / f"schemas/{schema}.schema.json")).validate(
                data
            )
        raw = path.parent / "runtime/declared-runtime-report.json"
        if raw.exists():
            Draft202012Validator(
                read(ROOT / "schemas/declared-communication-runtime.schema.json")
            ).validate(read(raw))
        self.assertEqual(verify(path)["status"], "passed")
        return path

    def check(self, path):
        return read(path.parent / "ecuc-stage.json")["checks"]["runtime.signal-tx"]

    def test_two_projects_and_portable_review_comparison(self):
        a = self.execute("a")
        b = self.execute("b")
        self.assertEqual(read(a)["status"], "passed")
        self.assertNotEqual(self.check(a)["run_id"], self.check(b)["run_id"])
        self.assertEqual(
            compare_project_reports(a, b, self.root / "comparison")["status"],
            "stable",
        )
        self.path = self.source / "transmitter.project.json"
        self.project = read(self.path)
        self.assertEqual(read(self.execute("tx"))["status"], "passed")
        shutil.rmtree(self.source)
        self.assertEqual(
            run_project_review(a, self.root / "review")["status"], "answered"
        )
        self.assertEqual(
            validate_project_comparison(
                self.root / "comparison/project-comparison.json"
            )["status"],
            "passed",
        )

    def test_static_failure_prevents_any_probe_or_exchange(self):
        self.mutate("<VALUE>8</VALUE>", "<VALUE>12</VALUE>")
        with patch(
            "automotive_workbench.ecuc_runtime.run_declared_communication"
        ) as runner:
            path = self.execute()
        runner.assert_not_called()
        self.assertEqual(read(path)["status"], "failed")
        self.assertEqual(self.check(path)["reason"], "static_acceptance_rejected")
        self.assertFalse((path.parent / "runtime").exists())

    def test_wrong_mapping_and_missing_ecuc_address_do_not_open_bus(self):
        for name in ["wrong", "missing"]:
            if name == "wrong":
                self.project["runtime"]["bindings"][0]["frame_id"] = 257
            else:
                self.project["runtime"]["bindings"][0]["frame_id"] = 256
                self.mutate("CanIfTxPduCanId</", "VendorId</")
            with patch(
                "automotive_workbench.ecuc_runtime.run_declared_communication"
            ) as runner:
                path = self.execute(name)
            runner.assert_not_called()
            self.assertNotEqual(read(path)["status"], "passed")
            self.assertFalse((path.parent / "runtime").exists())

    def test_unsupported_backend_is_recorded_blocked(self):
        with patch(
            "automotive_workbench.ecuc_runtime.run_declared_communication"
        ) as runner:
            path = self.execute(config=BusConfig("unsupported", "none"))
        runner.assert_not_called()
        self.assertEqual(self.check(path)["reason"], "unsupported_backend")
        self.assertEqual(read(path)["status"], "blocked")

    def test_timeout_and_wrong_id_actual_observations_fail(self):
        from automotive_workbench import declared_communication as runner

        original = runner.open_bus
        for fault, expected in [
            ("timeout", "receive_timeout"),
            ("wrong-id", "frame_identity_mismatch"),
        ]:
            calls = []

            def open_bus(config, filters):
                bus = original(config, filters)
                calls.append(bus)
                if len(calls) % 2 == 1 and fault == "timeout":
                    bus.send = lambda *args, **kwargs: None
                if len(calls) % 2 == 0 and fault == "wrong-id":
                    recv = bus.recv

                    def wrong(timeout=None):
                        frame = recv(timeout)
                        if frame is not None:
                            frame.arbitration_id += 1
                        return frame

                    bus.recv = wrong
                return bus

            with patch.object(runner, "open_bus", open_bus):
                path = self.execute(fault)
            self.assertEqual(self.check(path)["reason"], expected)
            self.assertEqual(read(path)["status"], "failed")

    def test_old_run_cannot_be_substituted_even_with_updated_runtime_hash(self):
        a, b = self.execute("a"), self.execute("b")
        old = (a.parent / "runtime/declared-runtime-report.json").read_bytes()
        (b.parent / "runtime/declared-runtime-report.json").write_bytes(old)
        record = b.parent / "runtime-link.json"
        data = read(record)
        data["runtime_sha256"] = sha(old)
        record.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "context"):
            verify(b)

    def test_forged_success_with_rehashed_wrong_frame_is_rejected(self):
        path = self.execute()
        rawpath = path.parent / "runtime/declared-runtime-report.json"
        raw = read(rawpath)
        raw["vectors"]["value-tx"]["observed"]["frame_id"] += 1
        rawpath.write_text(json.dumps(raw))
        recordpath = path.parent / "runtime-link.json"
        record = read(recordpath)
        record["runtime_sha256"] = sha(rawpath.read_bytes())
        recordpath.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "observation"):
            verify(path)

    def test_input_drift_missing_evidence_and_context_tampering_rejected(self):
        path = self.execute()
        for name in ["input", "missing", "context"]:
            dest = self.root / name
            shutil.copytree(path.parent, dest)
            if name == "input":
                p = dest / "inputs/runtime-vectors.json"
                p.write_text(p.read_text().replace("42", "43"))
            elif name == "missing":
                (dest / "runtime/declared-runtime-report.json").unlink()
            else:
                p = dest / "runtime-link.json"
                data = read(p)
                data["context"]["candidate_sha256"] = "a" * 64
                p.write_text(json.dumps(data))
            with self.subTest(name=name), self.assertRaises((ValueError, OSError)):
                verify(dest / "project-report.json")

    def test_invalid_links_rejected_before_output(self):
        original = copy.deepcopy(self.project)
        for kind in ["policy", "unbound", "address", "omitted"]:
            self.project = copy.deepcopy(original)
            b = self.project["runtime"]["bindings"][0]
            if kind == "policy":
                b["policy_ids"] = ["unknown"]
            elif kind == "unbound":
                b["vector_id"] = "missing"
            elif kind == "address":
                b["frame_id"] = True
            else:
                self.project["requirements"].pop()
            self.path.write_text(json.dumps(self.project))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                run_project(self.path, self.root / kind, BusConfig("virtual", "unused"))
            self.assertFalse((self.root / kind).exists())

    def test_json_boolean_substitution_does_not_match_frame_flag(self):
        path = self.execute()
        rawpath = path.parent / "runtime/declared-runtime-report.json"
        raw = read(rawpath)
        raw["vectors"]["value-tx"]["observed"]["is_extended_id"] = 0
        rawpath.write_text(json.dumps(raw))
        recordpath = path.parent / "runtime-link.json"
        record = read(recordpath)
        record["runtime_sha256"] = sha(rawpath.read_bytes())
        recordpath.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "observation"):
            verify(path)

    def test_runner_input_drift_is_not_overwritten_by_preflight(self):
        from automotive_workbench import ecuc_runtime

        original = ecuc_runtime.run_declared_communication

        def drift(*args, **kwargs):
            raw = original(*args, **kwargs)
            raw["plan"]["vectors"][0]["frame_id"] += 1
            return raw

        with patch.object(ecuc_runtime, "run_declared_communication", drift):
            with self.assertRaisesRegex(ValueError, "drifted"):
                self.execute()

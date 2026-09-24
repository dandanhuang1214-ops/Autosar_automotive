from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from automotive_workbench.communication_graph import (
    compile_graph,
    build_project_graph,
    compare_graphs,
    run_graph,
    verify_graph_report,
)

ROOT = Path(__file__).resolve().parents[1]


class CommunicationGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "thermal" / "project.json"
        shutil.copytree(ROOT / "examples/thermal_control", self.project.parent)

    def mutate(self, change, filename="bsw_intent.json"):
        path = self.project.parent / filename
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value), encoding="utf-8")

    def validate_schema(self, value):
        schemas = [json.loads(p.read_text()) for p in (ROOT / "schemas").glob("*.json")]
        registry = Registry().with_resources(
            (s["$id"], Resource.from_contents(s)) for s in schemas if "$id" in s
        )
        schema = next(
            s
            for s in schemas
            if s.get("properties", {}).get("schema_version", {}).get("const")
            == value["schema_version"]
        )
        Draft202012Validator(schema, registry=registry).validate(value)

    def test_two_projects_and_shared_route(self):
        for project, count in [
            (self.project, 14),
            (ROOT / "examples/window_control/project-declared.json", 8),
        ]:
            graph = build_project_graph(project)
            self.assertEqual(graph["status"], "passed")
            self.assertEqual(len(graph["nodes"]), count)
            self.assertEqual({n["direction"] for n in graph["nodes"]}, {"tx", "rx"})
            self.assertTrue(all(n["sources"] for n in graph["nodes"]))
            self.validate_schema(graph)
        route = next(
            n
            for n in build_project_graph(self.project)["nodes"]
            if n["name"] == "PduR_ThermalStatus"
        )
        self.assertEqual(
            len(route["sources"]), 3
        )  # two declared signal endpoints + DBC locator

    def test_unsupported_semantics_and_unmapped_layout(self):
        graph = build_project_graph(self.project)
        intent = json.loads((self.project.parent / "bsw_intent.json").read_text())
        messages = [
            n["attributes"]["dbc"] for n in graph["nodes"] if n["kind"] == "IPdu"
        ]
        messages[0]["unsupported"] = True
        rejected = compile_graph("thermal", intent, {"messages": messages})
        self.assertIn("GRAPH-UNSUPPORTED", {f["code"] for f in rejected["findings"]})
        path = self.project.parent / "thermal_control.dbc"
        path.write_text(
            path.read_text().replace(
                " SG_ FanDuty",
                ' SG_ Unmapped : 0|8@1+ (1,0) [0|255] "" TESTER\n SG_ FanDuty',
            ),
            encoding="utf-8",
        )
        rejected = build_project_graph(self.project)
        self.assertIn("GRAPH-LENGTH-LAYOUT", {f["code"] for f in rejected["findings"]})

    def test_missing_dbc_locator_is_not_claimed_and_parse_error_is_clean(self):
        self.mutate(lambda p: p["signals"][0].update(dbc_signal="Absent"))
        graph = build_project_graph(self.project)
        node = next(
            n for n in graph["nodes"] if n["name"] == "ComSig_CoolantTemperature"
        )
        self.assertFalse(any(s["artifact"] == "dbc" for s in node["sources"]))
        (self.project.parent / "thermal_control.dbc").write_text(
            "not a dbc", encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            build_project_graph(self.project)

    def test_rule_failures(self):
        original = (self.project.parent / "bsw_intent.json").read_bytes()
        mutations = [
            (
                "GRAPH-MISSING-REFERENCE",
                lambda p: p["signals"][0].update(i_pdu="Absent"),
            ),
            (
                "GRAPH-MISSING-REFERENCE",
                lambda p: p["signals"][0].update(dbc_signal="Absent"),
            ),
            (
                "GRAPH-DUPLICATE-IDENTITY",
                lambda p: p["signals"][1].update(
                    com_signal=p["signals"][0]["com_signal"]
                ),
            ),
            (
                "GRAPH-DUPLICATE-IDENTITY",
                lambda p: p["messages"].append(copy.deepcopy(p["messages"][0])),
            ),
            ("GRAPH-DIRECTION", lambda p: p["signals"][0].update(direction="rx")),
            ("GRAPH-DIRECTION", lambda p: p["messages"][0].update(direction="rx")),
            ("GRAPH-LENGTH-LAYOUT", lambda p: p["messages"][0].update(dlc=8)),
            ("GRAPH-LENGTH-LAYOUT", lambda p: p["signals"][0].update(bit_length=31)),
            (
                "GRAPH-ROUTE-ENDPOINT",
                lambda p: p["signals"][0].update(
                    canif_pdu=p["messages"][1]["canif_pdu"]
                ),
            ),
            (
                "GRAPH-DUPLICATE-IDENTITY",
                lambda p: p["signals"][2].update(
                    pdur_route=p["signals"][0]["pdur_route"]
                ),
            ),
        ]
        for code, mutation in mutations:
            with self.subTest(code=code):
                (self.project.parent / "bsw_intent.json").write_bytes(original)
                self.mutate(mutation)
                graph = build_project_graph(self.project)
                self.assertEqual(graph["status"], "failed")
                self.assertIn(code, {f["code"] for f in graph["findings"]})
                self.validate_schema(graph)

    def test_dbc_overlap_and_bounds(self):
        path = self.project.parent / "thermal_control.dbc"
        raw = path.read_text()
        self.assertIn("16|8", raw)
        for replacement in ["0|8", "31|8"]:
            path.write_text(raw.replace("16|8", replacement), encoding="utf-8")
            graph = build_project_graph(self.project)
            self.assertIn("GRAPH-LENGTH-LAYOUT", {f["code"] for f in graph["findings"]})

    def test_change_propagation_and_acceptance(self):
        before = build_project_graph(self.project)
        path = self.project.parent / "thermal_control.dbc"
        raw = path.read_text()
        path.write_text(raw.replace("(0.1,-40)", "(0.2,-40)", 1), encoding="utf-8")
        self.assertNotEqual(path.read_text(), raw)
        result = compare_graphs(before, build_project_graph(self.project))
        self.assertTrue(result["changes"])
        self.assertEqual(result["vectors"], ["thermal-status"])
        self.assertIn("thermal-status", result["requirements"])
        self.assertNotIn("pump-status", result["requirements"])
        self.assertNotIn("cooling-request", result["requirements"])
        kinds = {x["id"].split("/")[-2] for x in result["affected"]}
        self.assertEqual(kinds, {"ComSignal", "IPdu", "PduRRoute", "CanIfPdu"})
        edges = {
            frozenset((e["source"], e["target"]))
            for g in (result["baseline"], result["candidate"])
            for e in g["edges"]
        }
        for item in result["affected"]:
            self.assertEqual(item["path"][-1], item["id"])
            for left, right in zip(item["path"], item["path"][1:]):
                self.assertIn(frozenset((left, right)), edges)
        self.validate_schema(result)

    def test_reorder_is_not_semantic_change(self):
        before = build_project_graph(self.project)
        self.mutate(lambda p: p["signals"].reverse())
        result = compare_graphs(before, build_project_graph(self.project))
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["requirements"], [])

    def test_namespace_and_invalid_graph_refuse_comparison(self):
        before = build_project_graph(self.project)
        other = build_project_graph(
            ROOT / "examples/window_control/project-declared.json"
        )
        self.assertEqual(compare_graphs(before, other)["status"], "not-comparable")
        self.mutate(lambda p: p["signals"][0].update(i_pdu="missing"))
        self.assertEqual(
            compare_graphs(before, build_project_graph(self.project))["status"],
            "not-comparable",
        )

    def test_definition_and_contract_changes(self):
        before = build_project_graph(self.project)
        self.mutate(
            lambda p: p["vectors"][0]["signals"].update(FanDuty=50),
            "communication_vectors.json",
        )
        result = compare_graphs(before, build_project_graph(self.project))
        self.assertEqual(len(result["vectors"]), 3)
        self.assertEqual(len(result["requirements"]), 7)
        self.mutate(lambda p: p.update(source="changed"), "canonical_contract.json")
        result = compare_graphs(before, build_project_graph(self.project))
        self.assertTrue(any("contract changed" in x for x in result["unknowns"]))

    def test_renamed_objects_are_remove_add(self):
        before = build_project_graph(self.project)
        self.mutate(lambda p: p["signals"][0].update(com_signal="Renamed"))
        result = compare_graphs(before, build_project_graph(self.project))
        self.assertEqual({x["kind"] for x in result["changes"]}, {"removed", "added"})
        self.assertEqual(result["vectors"], ["thermal-status"])

    def test_saved_replay_migration_and_tampering(self):
        output = self.root / "report"
        run_graph(self.project, output, self.project)
        moved = self.root / "moved.json"
        shutil.copyfile(output / "report.json", moved)
        shutil.rmtree(self.project.parent)
        self.assertEqual(verify_graph_report(moved)["status"], "passed")
        original = json.loads(moved.read_text())
        for mutate in [
            lambda p: p["requirements"].append("forged"),
            lambda p: p["candidate"]["nodes"][0].update(direction="unknown"),
            lambda p: p["baseline"]["source_artifacts"][0].update(sha256="0" * 64),
        ]:
            payload = copy.deepcopy(original)
            mutate(payload)
            moved.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(verify_graph_report(moved)["status"], "failed")

    def test_cli_output_protection_and_readonly_verification(self):
        output = self.root / "cli"
        command = [
            sys.executable,
            "-m",
            "automotive_workbench.cli",
            "build-communication-graph",
            str(self.project),
            "--output",
            str(output),
        ]
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        report = output / "report.json"
        before = report.read_bytes()
        check = subprocess.run(
            [
                sys.executable,
                "-m",
                "automotive_workbench.cli",
                "verify-communication-graph",
                str(report),
            ],
            capture_output=True,
        )
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertEqual(before, report.read_bytes())

    def test_malformed_input_rejected_without_output(self):
        path = self.project.parent / "communication_vectors.json"
        path.write_text(
            '{"schema_version":"communication-vectors-0.1","vectors":[],"vectors":[]}',
            encoding="utf-8",
        )
        output = self.root / "absent"
        with self.assertRaises(ValueError):
            run_graph(self.project, output)
        self.assertFalse(output.exists())

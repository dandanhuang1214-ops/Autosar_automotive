from __future__ import annotations

import json
import copy
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from automotive_workbench.ecuc_communication import (
    build,
    run_communication,
    verify_communication,
)
from automotive_workbench.ecuc_project import NS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/ecuc-communication"


class EcucCommunicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        shutil.copytree(FIXTURE, self.source)
        self.project = self.source / "demo.dpa"

    def change(self, before: str, after: str) -> None:
        p = self.source / "modules.arxml"
        text = p.read_text(encoding="utf-8")
        self.assertIn(before, text)
        p.write_text(text.replace(before, after), encoding="utf-8")

    def report(self):
        return build(self.project)[0]

    def test_exact_tx_rx_chains_members_schema_and_locators(self) -> None:
        from jsonschema import Draft202012Validator

        r = self.report()
        self.assertEqual(r["status"], "resolved-in-scope")
        self.assertEqual(len(r["paths"]), 2)
        tx, rx = r["paths"]
        self.assertEqual((tx["direction"], rx["direction"]), ("tx", "rx"))
        self.assertEqual(
            tx["nodes"],
            [
                "/Demo/Com/PacketA",
                "/Demo/EcuC/A",
                "/Demo/PduR/RouteA",
                "/Demo/PduR/RouteA/Start",
                "/Demo/PduR/RouteA/End",
                "/Demo/EcuC/C",
                "/Demo/CanIf/PortA",
                "/Demo/CanIf/Buffer",
                "/Demo/CanIf/HandleA",
                "/Demo/Can/ObjectA",
                "/Demo/Can/Controller",
            ],
        )
        self.assertIn("/Demo/CanIf/HandleB", rx["nodes"])
        self.assertNotIn("/Demo/CanIf/Buffer", rx["nodes"])
        self.assertEqual(
            rx["members"],
            [
                {"node": "/Demo/Com/GroupB", "group": ""},
                {"node": "/Demo/Com/GroupB/ValueB", "group": "/Demo/Com/GroupB"},
            ],
        )
        for edge in r["edges"]:
            self.assertEqual(edge["resolution"], "resolved")
            # Resolve the emitted namespace-local XPath back to its exact XML element.
            tree = ET.parse(self.source / edge["source"]["file"])
            steps = edge["source"]["xpath"].split("/")[2:]
            xml_path = "./" + "/".join("a:" + part for part in steps)
            element = tree.find(xml_path, {"a": NS})
            self.assertIsNotNone(element)
            if edge["kind"] == "reference":
                self.assertEqual(
                    element.findtext("{" + NS + "}VALUE-REF"), edge["target"]
                )
        schema = json.loads(
            (ROOT / "schemas/ecuc-communication.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(r)
        r["paths"][0]["unexpected"] = True
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(r)))

    def test_names_do_not_determine_direction_or_links(self) -> None:
        self.change("PacketA", "MisleadingRxName")
        self.change("ObjectA", "ReceiveLookingName")
        r = self.report()
        self.assertEqual(r["status"], "resolved-in-scope")
        self.assertEqual(r["paths"][0]["direction"], "tx")
        self.assertIn("/Demo/Can/ReceiveLookingName", r["paths"][0]["nodes"])

    def test_missing_wrong_type_and_external_refs_are_not_completed(self) -> None:
        for target, resolution in [
            ("/Demo/Can/Missing", "missing"),
            ("/Demo/Can/Controller", "wrong-type"),
            ("/Other/ObjectA", "unassessed"),
            ("", "empty"),
        ]:
            with self.subTest(target=target):
                original = (FIXTURE / "modules.arxml").read_text(encoding="utf-8")
                (self.source / "modules.arxml").write_text(
                    original.replace("/Demo/Can/ObjectA", target), encoding="utf-8"
                )
                r = self.report()
                self.assertEqual(r["paths"][0]["status"], "partial")
                self.assertEqual(r["paths"][1]["status"], "resolved")
                self.assertIn(resolution, [e["resolution"] for e in r["edges"]])

    def test_direction_and_routing_endpoint_failures(self) -> None:
        for before, after in [
            (">SEND<", ">RECEIVE<"),
            (">TRANSMIT<", ">RECEIVE<"),
            ("/Demo/EcuC/C</VALUE-REF>", "/Demo/EcuC/D</VALUE-REF>"),
        ]:
            with self.subTest(before=before):
                (self.source / "modules.arxml").write_bytes(
                    (FIXTURE / "modules.arxml").read_bytes()
                )
                # For routing failure change only the PduR endpoint, not the CanIf reference.
                p = self.source / "modules.arxml"
                p.write_text(
                    p.read_text(encoding="utf-8").replace(before, after, 1),
                    encoding="utf-8",
                )
                self.assertEqual(self.report()["paths"][0]["status"], "partial")

    def test_duplicate_identity_is_ambiguous(self) -> None:
        self.change(
            "<SHORT-NAME>ObjectB</SHORT-NAME>", "<SHORT-NAME>ObjectA</SHORT-NAME>"
        )
        r = self.report()
        self.assertEqual(r["status"], "partial")
        self.assertIn("ambiguous", [e["resolution"] for e in r["edges"]])
        self.assertTrue(all(p["status"] == "partial" for p in r["paths"]))

    def test_fanout_preserves_each_destination_and_ambiguous_canif_is_partial(
        self,
    ) -> None:
        p = self.source / "modules.arxml"
        tree = ET.parse(p)
        def tag(name: str) -> str:
            return "{" + NS + "}" + name
        all_nodes = tree.findall(".//" + tag("ECUC-CONTAINER-VALUE"))
        route = next(c for c in all_nodes if c.findtext(tag("SHORT-NAME")) == "RouteA")
        end = next(
            c
            for c in route.findall(".//" + tag("ECUC-CONTAINER-VALUE"))
            if c.findtext(tag("SHORT-NAME")) == "End"
        )
        extra = copy.deepcopy(end)
        extra.find(tag("SHORT-NAME")).text = "SecondDestination"
        route.find(tag("SUB-CONTAINERS")).append(extra)
        tree.write(p, encoding="utf-8", xml_declaration=True)
        r = self.report()
        self.assertEqual(len(r["paths"]), 3)
        self.assertTrue(all(c["status"] == "resolved" for c in r["paths"]))
        self.assertIn("/Demo/PduR/RouteA/SecondDestination", r["paths"][1]["nodes"])
        # Two configurations claiming the same CanIf global PDU are not silently chosen.
        module = next(
            m
            for m in tree.findall(".//" + tag("ECUC-MODULE-CONFIGURATION-VALUES"))
            if m.findtext(tag("SHORT-NAME")) == "CanIf"
        )
        port = next(c for c in all_nodes if c.findtext(tag("SHORT-NAME")) == "PortA")
        duplicate = copy.deepcopy(port)
        duplicate.find(tag("SHORT-NAME")).text = "AlternativePort"
        module.find(tag("CONTAINERS")).append(duplicate)
        tree.write(p, encoding="utf-8", xml_declaration=True)
        r = self.report()
        self.assertTrue(
            all(c["status"] == "partial" for c in r["paths"] if c["direction"] == "tx")
        )

    def test_duplicate_required_reference_and_conditional_direction(self) -> None:
        p = self.source / "modules.arxml"
        tree = ET.parse(p)
        ns = {"a": NS}
        for group in tree.findall(".//a:REFERENCE-VALUES", ns):
            for ref in list(group):
                if ref.findtext("a:DEFINITION-REF", "", ns).endswith(
                    "/CanIfHthIdSymRef"
                ):
                    group.append(copy.deepcopy(ref))
        tree.write(p, encoding="utf-8", xml_declaration=True)
        self.assertEqual(self.report()["paths"][0]["status"], "partial")
        p.write_bytes((FIXTURE / "modules.arxml").read_bytes())
        self.change("<VALUE>SEND</VALUE>", "<VALUE>SEND</VALUE><VARIATION-POINT/>")
        self.assertEqual(self.report()["paths"][0]["direction"], "unknown")

    def test_unknown_reference_and_variant_are_explicit(self) -> None:
        self.change("CanIfHthIdSymRef", "VendorHardwareLink")
        r = self.report()
        self.assertEqual(r["paths"][0]["status"], "partial")
        self.assertTrue(
            any(
                x["definition"].endswith("/VendorHardwareLink")
                for x in r["unassessed_references"]
            )
        )
        (self.source / "modules.arxml").write_bytes(
            (FIXTURE / "modules.arxml").read_bytes()
        )
        self.change(
            "<SHORT-NAME>ObjectA</SHORT-NAME>",
            "<SHORT-NAME>ObjectA</SHORT-NAME><VARIATION-POINT/>",
        )
        r = self.report()
        self.assertEqual(r["paths"][0]["status"], "partial")
        self.assertIn("conditional", [e["resolution"] for e in r["edges"]])

    def test_unselected_module_and_no_com_are_not_success(self) -> None:
        p = self.source / "collection.arxml"
        p.write_text(
            p.read_text(encoding="utf-8").replace("/Demo/Can<", "/Demo/Unknown<"),
            encoding="utf-8",
        )
        r = self.report()
        self.assertEqual(r["status"], "partial")
        self.assertIn("unassessed", [e["resolution"] for e in r["edges"]])
        self.change("/Synthetic/ComIPdu<", "/Synthetic/VendorIPdu<")
        self.assertEqual(self.report()["status"], "no-paths")

    def test_replay_after_move_and_all_tamper_classes(self) -> None:
        out = self.root / "out"
        run_communication(self.project, out)
        shutil.rmtree(self.source)
        moved = self.root / "moved"
        out.rename(moved)
        p = moved / "ecuc-communication.json"
        self.assertEqual(verify_communication(p)["status"], "passed")
        original = p.read_bytes()
        report = json.loads(original)
        report["paths"][0]["direction"] = "rx"
        p.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_communication(p)
        p.write_bytes(original)
        extra = moved / "snapshot/extra.txt"
        extra.write_text("extra")
        with self.assertRaisesRegex(ValueError, "inventory"):
            verify_communication(p)
        extra.unlink()
        source = moved / "snapshot/modules.arxml"
        source.write_bytes(source.read_bytes().replace(b">SEND<", b">RECEIVE<"))
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_communication(p)

    def test_output_protection_and_malformed_report(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            run_communication(self.project, self.source / "output")
        out = self.root / "out"
        out.mkdir()
        (out / "keep").write_text("keep")
        with self.assertRaisesRegex(ValueError, "empty"):
            run_communication(self.project, out)
        self.assertEqual((out / "keep").read_text(), "keep")
        p = self.root / "bad.json"
        for value in [
            None,
            [],
            {},
            {"schema_version": "ecuc-communication-0.1", "project": 3},
        ]:
            p.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                verify_communication(p)

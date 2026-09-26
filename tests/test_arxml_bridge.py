from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from jsonschema import Draft202012Validator

from automotive_workbench.arxml_bridge import (
    NS,
    compare_imports,
    import_arxml,
    import_bytes,
    run_arxml,
    verify_report,
)
from scripts.run_arxml_scenarios import EVENT_ID, mutations

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/generate_arxml/xml"
DATA = (FIXTURE / "model.arxml").read_bytes()


def imported(data: bytes = DATA) -> dict:
    return import_bytes(data, "model.arxml", {"status": "unrecorded"})


class ArxmlBridgeTests(unittest.TestCase):
    def test_malformed_saved_reports_are_rejected(self) -> None:
        for report in [
            [],
            {},
            {"schema_version": "arxml-import-0.1", "source": []},
            {"schema_version": "arxml-comparison-0.1", "baseline": None},
        ]:
            with self.subTest(report=report), self.assertRaises(ValueError):
                verify_report(report)

    def test_real_export_and_source_binding(self) -> None:
        report = import_arxml(FIXTURE / "model.arxml", FIXTURE / "provenance.json")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["objects"]), 36)
        self.assertEqual(len(report["references"]), 25)
        self.assertEqual(report["unsupported"], [])
        self.assertIn("COM, IPdu, PduR", " ".join(report["boundaries"]))
        verify_report(report)
        Draft202012Validator(
            json.loads((ROOT / "schemas/arxml-import.schema.json").read_text())
        ).validate(report)

    def test_golden_dangling_and_exact_period_change(self) -> None:
        modified = mutations(DATA)
        dangling = imported(modified["dangling"])
        self.assertEqual(
            [f["code"] for f in dangling["findings"]], ["ARXML-DANGLING-REF"]
        )
        self.assertEqual(
            compare_imports(imported(), dangling)["status"], "not-comparable"
        )
        diff = compare_imports(imported(), imported(modified["period-change"]))
        self.assertEqual([c["id"] for c in diff["changes"]], [EVENT_ID])
        change = diff["changes"][0]
        for side, value in [("before", "0.01"), ("after", "0.02")]:
            self.assertEqual(
                next(
                    f["value"]
                    for f in change[side]["facts"]
                    if f["path"] == "./PERIOD[1]"
                ),
                value,
            )
        verify_report(diff)
        Draft202012Validator(
            json.loads((ROOT / "schemas/arxml-comparison.schema.json").read_text())
        ).validate(diff)

    def test_uuid_formatting_and_package_order_do_not_change_semantics(self) -> None:
        root = ET.fromstring(DATA)
        for node in root.iter():
            if "UUID" in node.attrib:
                node.set("UUID", "different")
        packages = root.find(f"{{{NS}}}AR-PACKAGES")
        assert packages is not None
        packages[:] = list(reversed(list(packages)))
        report = compare_imports(imported(), imported(ET.tostring(root)))
        self.assertEqual(report["status"], "stable")
        self.assertTrue(report["source_bytes_changed"])

    def test_dest_and_duplicate_identity_fail(self) -> None:
        for old, new, code in [
            (b'DEST="SW-BASE-TYPE"', b'DEST="DATA-CONSTR"', "ARXML-DEST-MISMATCH"),
            (
                b"<SHORT-NAME>App_RequestedDirection</SHORT-NAME>",
                b"<SHORT-NAME>App_WindowPosition</SHORT-NAME>",
                "ARXML-DUPLICATE",
            ),
            (
                b"<SHORT-NAME>App_RequestedDirection</SHORT-NAME>",
                b"<SHORT-NAME>invalid/name</SHORT-NAME>",
                "ARXML-IDENTITY",
            ),
        ]:
            with self.subTest(code=code):
                result = imported(DATA.replace(old, new))
                self.assertEqual(result["status"], "failed")
                self.assertIn(code, [f["code"] for f in result["findings"]])

    def test_unsupported_elements_and_attributes_never_compare_stable(self) -> None:
        for old, new in [
            (
                b"<PERIOD>0.01</PERIOD>",
                b"<PERIOD>0.01</PERIOD><VENDOR-THING>1</VENDOR-THING>",
            ),
            (b"<PERIOD>", b'<PERIOD VENDOR="x">'),
            (b"<PERIOD>", b'<PERIOD xmlns="urn:foreign">'),
        ]:
            with self.subTest(new=new):
                result = imported(DATA.replace(old, new))
                self.assertEqual(result["coverage"], "partial")
                self.assertTrue(result["unsupported"])
                self.assertEqual(
                    compare_imports(result, result)["status"], "not-comparable"
                )

    def test_version_xml_dtd_and_resource_limits(self) -> None:
        for data in [
            DATA.replace(b"AUTOSAR_4-3-0.xsd", b"AUTOSAR_4-4-0.xsd"),
            DATA.replace(
                b"http://autosar.org/schema/r4.0", b"http://autosar.org/schema/r3.0"
            ),
            b"<AUTOSAR>",
            b'<!DOCTYPE x [<!ENTITY x "abc">]>' + DATA,
            DATA.decode().encode("utf-16"),
            b"x" * (4 * 1024 * 1024 + 1),
            DATA.replace(b"<PERIOD>0.01</PERIOD>", b"<A>" * 65 + b"</A>" * 65),
        ]:
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                imported(data)

    def test_embedded_source_and_conclusions_tamper_rejected(self) -> None:
        for key, value in [
            ("status", "failed"),
            ("objects", []),
            ("references", []),
            ("unsupported", [{}]),
        ]:
            report = imported()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_report(report)
        for key in ["sha256", "content_base64"]:
            report = imported()
            report["source"][key] = "corrupt"
            with self.assertRaises(ValueError):
                verify_report(report)
        report = compare_imports(imported(), imported(mutations(DATA)["period-change"]))
        report["changes"] = []
        with self.assertRaises(ValueError):
            verify_report(report)

    def test_provenance_mismatch_and_output_protection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "changed.arxml"
            source.write_bytes(mutations(DATA)["period-change"])
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                run_arxml(
                    source, root / "output", provenance=FIXTURE / "provenance.json"
                )
            self.assertFalse((root / "output").exists())
            protected = root / "protected"
            protected.mkdir()
            (protected / "user.txt").write_text("preserve")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run_arxml(source, protected)
            self.assertEqual((protected / "user.txt").read_text(), "preserve")

    def test_cli_errors_do_not_create_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.arxml").write_bytes(b"<AUTOSAR>")
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "automotive_workbench.cli",
                    "import-arxml",
                    str(root / "bad.arxml"),
                    "--output",
                    str(root / "out"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 1)
            self.assertEqual(json.loads(process.stdout)["status"], "error")
            self.assertFalse((root / "out").exists())

    def test_added_removed_and_type_changes(self) -> None:
        base = imported()
        root = ET.fromstring(DATA)
        elements = root.find(f".//{{{NS}}}ELEMENTS")
        assert elements is not None
        extra = ET.SubElement(elements, f"{{{NS}}}UNIT")
        ET.SubElement(extra, f"{{{NS}}}SHORT-NAME").text = "ExtraUnit"
        other = imported(ET.tostring(root))
        self.assertEqual(compare_imports(base, other)["changes"][0]["change"], "added")
        self.assertEqual(
            compare_imports(other, base)["changes"][0]["change"], "removed"
        )
        corrupted = copy.deepcopy(other)
        corrupted["objects"][0]["kind"] = "different"
        with self.assertRaises(ValueError):
            verify_report(corrupted)


if __name__ == "__main__":
    unittest.main()

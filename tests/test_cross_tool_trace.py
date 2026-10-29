from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest
from xml.etree import ElementTree as ET

from automotive_workbench.cross_tool_trace import compare_traces, trace_cross_tool, verify_trace, verify_impact
from automotive_workbench.davinci_mapping import audit_mappings


ROOT = Path(__file__).resolve().parents[1]
NS = "http://autosar.org/schema/r4.0"


def fixture(base: Path, source: Path, signal: str = "Ready", direction: str = "Tx", bind: bool = True) -> Path:
    shutil.copytree(source, base)
    modules = base / "modules.arxml"
    root = ET.parse(modules).getroot()
    for node in root.findall(".//{*}ECUC-CONTAINER-VALUE"):
        if node.findtext("{*}SHORT-NAME") == "ValueA":
            if bind:
                refs = ET.SubElement(node, f"{{{NS}}}REFERENCE-VALUES")
                ref = ET.SubElement(refs, f"{{{NS}}}ECUC-REFERENCE-VALUE")
                ET.SubElement(ref, f"{{{NS}}}DEFINITION-REF").text = "/Synthetic/ComSignal/ComSystemTemplateSystemSignalRef"
                ET.SubElement(ref, f"{{{NS}}}VALUE-REF").text = "/PDU/Packet/Ready"
            break
    modules.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
    developer = base / "developer.arxml"
    developer.write_text(f'''<AUTOSAR xmlns="{NS}"><AR-PACKAGES>
      <AR-PACKAGE><SHORT-NAME>Signal</SHORT-NAME><ELEMENTS><SYSTEM-SIGNAL><SHORT-NAME>{signal}</SHORT-NAME></SYSTEM-SIGNAL></ELEMENTS></AR-PACKAGE>
      <AR-PACKAGE><SHORT-NAME>Components</SHORT-NAME><ELEMENTS><APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>Node</SHORT-NAME><PORTS><{'P' if direction == 'Tx' else 'R'}-PORT-PROTOTYPE><SHORT-NAME>Out</SHORT-NAME></{'P' if direction == 'Tx' else 'R'}-PORT-PROTOTYPE></PORTS></APPLICATION-SW-COMPONENT-TYPE></ELEMENTS></AR-PACKAGE>
      <AR-PACKAGE><SHORT-NAME>Interfaces</SHORT-NAME><ELEMENTS><SENDER-RECEIVER-INTERFACE><SHORT-NAME>State</SHORT-NAME><DATA-ELEMENTS><VARIABLE-DATA-PROTOTYPE><SHORT-NAME>Ready</SHORT-NAME></VARIABLE-DATA-PROTOTYPE></DATA-ELEMENTS></SENDER-RECEIVER-INTERFACE></ELEMENTS></AR-PACKAGE>
      <AR-PACKAGE><SHORT-NAME>System</SHORT-NAME><ELEMENTS><SYSTEM><SHORT-NAME>Vehicle</SHORT-NAME><MAPPINGS><SENDER-RECEIVER-TO-SIGNAL-MAPPING><DATA-ELEMENT-IREF>
        <CONTEXT-PORT-REF DEST="{'P' if direction == 'Tx' else 'R'}-PORT-PROTOTYPE">/Components/Node/Out</CONTEXT-PORT-REF>
        <TARGET-DATA-PROTOTYPE-REF DEST="VARIABLE-DATA-PROTOTYPE">/Interfaces/State/Ready</TARGET-DATA-PROTOTYPE-REF>
        </DATA-ELEMENT-IREF><SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Signal/{signal}</SYSTEM-SIGNAL-REF>
        </SENDER-RECEIVER-TO-SIGNAL-MAPPING></MAPPINGS></SYSTEM></ELEMENTS></AR-PACKAGE>
      </AR-PACKAGES></AUTOSAR>''', encoding="utf-8")
    system = base / "system.arxml"
    system.write_text(f'''<AUTOSAR xmlns="{NS}"><AR-PACKAGES>
      <AR-PACKAGE><SHORT-NAME>ISignal</SHORT-NAME><ELEMENTS><I-SIGNAL><SHORT-NAME>Ready</SHORT-NAME><SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Signal/{signal}</SYSTEM-SIGNAL-REF></I-SIGNAL></ELEMENTS></AR-PACKAGE>
      <AR-PACKAGE><SHORT-NAME>PDU</SHORT-NAME><ELEMENTS><I-SIGNAL-I-PDU><SHORT-NAME>Packet</SHORT-NAME><I-SIGNAL-TO-I-PDU-MAPPINGS><I-SIGNAL-TO-I-PDU-MAPPING><SHORT-NAME>Ready</SHORT-NAME><I-SIGNAL-REF DEST="I-SIGNAL">/ISignal/Ready</I-SIGNAL-REF></I-SIGNAL-TO-I-PDU-MAPPING></I-SIGNAL-TO-I-PDU-MAPPINGS></I-SIGNAL-I-PDU></ELEMENTS></AR-PACKAGE>
      </AR-PACKAGES></AUTOSAR>''', encoding="utf-8")
    audit_mappings([developer], base / "mapping.json")
    return base / "demo.dpa"


class CrossToolTraceTests(unittest.TestCase):
    def test_two_distinct_public_projects_and_semantic_change(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            sources = [ROOT / "tests/fixtures/ecuc-communication", ROOT / "examples/ecuc_diagnostic/transmitter"]
            for index, source in enumerate(sources):
                before = root / f"project-{index}-before"
                after = root / f"project-{index}-after"
                fixture(before, source)
                fixture(after, source, signal="Alternate")
                old = trace_cross_tool(before / "mapping.json", before / "system.arxml", before / "demo.dpa", before / "trace.json")
                new = trace_cross_tool(after / "mapping.json", after / "system.arxml", after / "demo.dpa", after / "trace.json")
                self.assertEqual(old["status"], "resolved-in-scope")
                self.assertEqual(new["status"], "resolved-in-scope")
                self.assertEqual(verify_trace(before / "trace.json")["status"], "passed")
                same = compare_traces(before / "trace.json", before / "trace.json", root / f"same-{index}.json")
                self.assertEqual(same["status"], "unchanged")
                change = compare_traces(before / "trace.json", after / "trace.json", root / f"change-{index}.json")
                self.assertEqual(change["changes"][0]["fields"], ["system_signal"])
                self.assertEqual(verify_impact(root / f"change-{index}.json")["status"], "passed")

    def test_missing_foreign_reference_is_unassessed(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory) / "project"
            fixture(base, ROOT / "tests/fixtures/ecuc-communication", bind=False)
            result = trace_cross_tool(base / "mapping.json", base / "system.arxml", base / "demo.dpa", base / "trace.json")
            self.assertEqual(result["links"][0]["status"], "unassessed")

    def test_direction_conflict_is_not_resolved(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory) / "project"
            fixture(base, ROOT / "tests/fixtures/ecuc-communication", direction="Rx")
            result = trace_cross_tool(base / "mapping.json", base / "system.arxml", base / "demo.dpa", base / "trace.json")
            self.assertEqual(result["links"][0]["status"], "direction-conflict")

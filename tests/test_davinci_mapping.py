from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from automotive_workbench.davinci_mapping import audit_mappings, verify_mapping_audit


def _arxml(mapping_signal: str) -> str:
    return f'''<AUTOSAR xmlns="http://autosar.org/schema/r4.0"><AR-PACKAGES>
      <AR-PACKAGE><SHORT-NAME>Signal</SHORT-NAME><ELEMENTS>
        <SYSTEM-SIGNAL><SHORT-NAME>Ready</SHORT-NAME></SYSTEM-SIGNAL>
      </ELEMENTS></AR-PACKAGE>
      <AR-PACKAGE><SHORT-NAME>Interface</SHORT-NAME><ELEMENTS>
        <SENDER-RECEIVER-INTERFACE><SHORT-NAME>State</SHORT-NAME><DATA-ELEMENTS>
          <VARIABLE-DATA-PROTOTYPE><SHORT-NAME>Ready</SHORT-NAME></VARIABLE-DATA-PROTOTYPE>
        </DATA-ELEMENTS></SENDER-RECEIVER-INTERFACE>
      </ELEMENTS></AR-PACKAGE>
      <AR-PACKAGE><SHORT-NAME>Component</SHORT-NAME><ELEMENTS>
        <APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>Node</SHORT-NAME><PORTS>
          <P-PORT-PROTOTYPE><SHORT-NAME>Out</SHORT-NAME></P-PORT-PROTOTYPE>
        </PORTS></APPLICATION-SW-COMPONENT-TYPE>
      </ELEMENTS></AR-PACKAGE>
      <AR-PACKAGE><SHORT-NAME>System</SHORT-NAME><ELEMENTS><SYSTEM><SHORT-NAME>Vehicle</SHORT-NAME>
        <MAPPINGS><SENDER-RECEIVER-TO-SIGNAL-MAPPING><DATA-ELEMENT-IREF>
          <CONTEXT-PORT-REF DEST="P-PORT-PROTOTYPE">/Component/Node/Out</CONTEXT-PORT-REF>
          <TARGET-DATA-PROTOTYPE-REF DEST="VARIABLE-DATA-PROTOTYPE">/Interface/State/Ready</TARGET-DATA-PROTOTYPE-REF>
        </DATA-ELEMENT-IREF><SYSTEM-SIGNAL-REF DEST="SYSTEM-SIGNAL">/Signal/{mapping_signal}</SYSTEM-SIGNAL-REF>
        </SENDER-RECEIVER-TO-SIGNAL-MAPPING></MAPPINGS>
      </SYSTEM></ELEMENTS></AR-PACKAGE>
    </AR-PACKAGES></AUTOSAR>'''


class MappingAuditTests(unittest.TestCase):
    def test_audit_resolves_full_references(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.arxml"
            source.write_text(_arxml("Ready"), encoding="utf-8")
            report = audit_mappings([source], Path(directory) / "report.json")
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["summary"], {"total": 1, "resolved": 1})
            self.assertEqual(report["mappings"][0]["direction"], "Tx")
            self.assertEqual(verify_mapping_audit(Path(directory) / "report.json")["status"], "passed")
            source.write_text(_arxml("Missing"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                verify_mapping_audit(Path(directory) / "report.json")

    def test_audit_exposes_dangling_signal(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.arxml"
            source.write_text(_arxml("Missing"), encoding="utf-8")
            report = audit_mappings([source], Path(directory) / "report.json")
            self.assertEqual(report["status"], "attention-required")
            self.assertEqual(report["mappings"][0]["unresolved"], ["system_signal"])

    def test_audit_exposes_port_direction_conflict(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.arxml"
            source.write_text(_arxml("Ready").replace('DEST="P-PORT-PROTOTYPE"', 'DEST="R-PORT-PROTOTYPE"'), encoding="utf-8")
            report = audit_mappings([source], Path(directory) / "report.json")
            self.assertEqual(report["status"], "attention-required")
            self.assertEqual(report["mappings"][0]["unresolved"], ["port"])

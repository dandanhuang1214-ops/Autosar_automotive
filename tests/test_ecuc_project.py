from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from automotive_workbench.ecuc_project import inspect, run_inspection, verify_inspection, xml
from scripts.run_p24_assessment import cohort_context

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/ecuc-project'


class EcucProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        shutil.copytree(FIXTURE, self.source)
        self.project = self.source / 'demo.dpa'

    def change(self, old: str, new: str) -> None:
        p = self.source / 'modules.arxml'
        p.write_text(p.read_text().replace(old, new), encoding='utf-8')

    def test_selection_external_scope_and_schema(self) -> None:
        from jsonschema import Draft202012Validator
        report, _ = inspect(self.project)
        self.assertEqual(report['status'], 'no-issues-in-scope')
        self.assertEqual([m['path'] for m in report['modules']], ['/Demo/Os', '/Demo/Rte'])
        self.assertEqual(report['unselected_module_paths'], ['/Demo/Unused'])
        self.assertEqual(report['references']['unassessed'], 1)
        self.assertEqual(report['references']['resolved'], 1)
        self.assertFalse(report['findings'])
        schema = json.loads((ROOT / 'schemas/ecuc-project-inspection.schema.json').read_text())
        Draft202012Validator(schema).validate(report)
        forged = {**report, 'sources': [{**report['sources'][0], 'sha256': 'bad'}]}
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(forged)))

    def test_unbound_and_missing_targets_have_source_locators(self) -> None:
        self.change('/Demo/Os/Task10ms', '/Demo/Os/Absent')
        report, _ = inspect(self.project)
        self.assertEqual([f['code'] for f in report['findings']], ['ECUC-MISSING-REFERENCE'])
        self.assertTrue(report['findings'][0]['source']['xpath'].endswith('ECUC-REFERENCE-VALUE[2]'))
        self.assertIn('/REFERENCE-VALUES[1]/', report['findings'][0]['source']['xpath'])
        self.change('/Demo/Os/Absent', '')
        report, _ = inspect(self.project)
        self.assertEqual([f['code'] for f in report['findings']], ['ECUC-TASK-UNBOUND'])

    def test_duplicate_paths_are_not_silently_overwritten(self) -> None:
        self.change('</CONTAINERS>', '<ECUC-CONTAINER-VALUE><SHORT-NAME>Task10ms</SHORT-NAME><DEFINITION-REF>/Synthetic/OsTask</DEFINITION-REF></ECUC-CONTAINER-VALUE></CONTAINERS>')
        report, _ = inspect(self.project)
        self.assertIn('ECUC-AMBIGUOUS-PATH', [f['code'] for f in report['findings']])
        self.assertEqual(report['references']['ambiguous'], 1)

    def test_unresolved_selected_module_is_reported(self) -> None:
        self.change('<SHORT-NAME>Os</SHORT-NAME>', '<SHORT-NAME>Other</SHORT-NAME>')
        report, _ = inspect(self.project)
        self.assertIn('ECUC-MODULE-SELECTION', [f['code'] for f in report['findings']])

    def test_relocation_and_tamper_rejection(self) -> None:
        out = self.root / 'out'
        run_inspection(self.project, out)
        shutil.rmtree(self.source)
        moved = self.root / 'moved'
        out.rename(moved)
        path = moved / 'ecuc-inspection.json'
        self.assertEqual(verify_inspection(path)['status'], 'passed')
        original = path.read_text()
        report = json.loads(original)
        report['references']['resolved'] = True
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'differs'):
            verify_inspection(path)
        path.write_text(original)
        (moved / 'snapshot/extra.txt').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_inspection(path)
        (moved / 'snapshot/extra.txt').unlink()
        (moved / 'snapshot/modules.arxml').write_text('<broken>')
        with self.assertRaises(ValueError):
            verify_inspection(path)

    def test_escaping_input_and_source_output_are_rejected(self) -> None:
        for value in ['../outside.arxml', 'C:\\outside.arxml', '/outside.arxml']:
            text = (FIXTURE / 'demo.dpa').read_text().replace('modules.arxml', value)
            self.project.write_text(text)
            with self.assertRaises(ValueError):
                run_inspection(self.project, self.root / 'out')
            self.assertFalse((self.root / 'out').exists())
        self.project.write_text((FIXTURE / 'demo.dpa').read_text())
        with self.assertRaisesRegex(ValueError, 'outside'):
            run_inspection(self.project, self.source / 'output')
        out = self.root / 'out'
        out.mkdir()
        (out / 'keep').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'empty'):
            run_inspection(self.project, out)
        self.assertEqual((out / 'keep').read_text(), 'keep')

    def test_xml_entity_and_namespace_rejection(self) -> None:
        for data in [b'<!DOCTYPE AUTOSAR [<!ENTITY x "value">]><AUTOSAR/>', b'<AUTOSAR/>', b'<broken', b'\xff']:
            with self.assertRaises(ValueError):
                xml(data)

    def test_malformed_report_is_rejected_as_input_error(self) -> None:
        path = self.root / 'malformed.json'
        for report in [None, [], 1, {}, {'project': []}, {'project': 5}]:
            with self.subTest(report=report):
                path.write_text(json.dumps(report), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'object with a project filename'):
                    verify_inspection(path)

    def test_historical_regression_does_not_claim_independence(self) -> None:
        manifest = json.loads((ROOT / 'tests/fixtures/p24-held-out-0.1.json').read_text())
        with self.assertRaisesRegex(ValueError, 'Frozen'):
            cohort_context(manifest)
        context = cohort_context(manifest, historical=True)
        self.assertEqual(context['split'], 'historical-regression')
        self.assertFalse(context['freeze_verified'])
        self.assertEqual(context['original_freeze'], manifest['freeze'])
        self.assertIn('src/automotive_workbench/ecuc_project.py', context['current_runtime_sha256'])

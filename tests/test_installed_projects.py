from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_installed_projects import assert_isolated, inventory, prepare_examples, run

ROOT = Path(__file__).resolve().parents[1]


class InstalledProjectsTests(unittest.TestCase):
    def test_rejects_checkout_and_foreign_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout, environment = root / "checkout", root / "venv"
            for origin in (checkout / "src/pkg.py", root / "global/pkg.py"):
                with self.assertRaisesRegex(RuntimeError, "isolated installed"):
                    assert_isolated({"module": str(origin), "prefix": str(environment)}, checkout, environment)
            with self.assertRaisesRegex(RuntimeError, "interpreter"):
                assert_isolated({"module": str(environment / "pkg.py"), "prefix": str(root)}, checkout, environment)
            assert_isolated({"module": str(environment / "pkg.py"), "prefix": str(environment)}, checkout, environment)

    def test_sample_package_is_complete_and_mutation_is_owned(self) -> None:
        before = inventory(ROOT / "examples/thermal_control")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "examples"
            prepare_examples(ROOT, target)
            for name in ("window", "thermal", "scale-failure"):
                project = json.loads((target / name / "project.json").read_text())
                self.assertEqual(project["schema_version"], "workbench-project-0.3")
                self.assertEqual(set(inventory(target / name)), {"project.json", *project["inputs"].values()})
            base, changed = inventory(target / "thermal"), inventory(target / "scale-failure")
            self.assertEqual([name for name in base if base[name] != changed[name]], ["thermal_control.dbc"])
        self.assertEqual(before, inventory(ROOT / "examples/thermal_control"))

    def test_refuses_missing_mutation_site(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_examples(ROOT, root / "examples")
            # Prepare a minimal checkout with a different DBC; never mutate repository data.
            (root / "examples/window").rename(root / "examples/window_control")
            window = root / "examples/window_control"
            (window / "project.json").rename(window / "project-declared.json")
            (root / "examples/scale-failure").rename(root / "examples/thermal_control")
            dbc = root / "examples/thermal_control/thermal_control.dbc"
            dbc.write_text(dbc.read_text().replace("(0.1,-40)", "(0.2,-40)"))
            with self.assertRaisesRegex(RuntimeError, "mutation site"):
                prepare_examples(root, root / "new")

    def test_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            marker = output / "saved.txt"
            marker.write_text("keep")
            with self.assertRaisesRegex(ValueError, "empty or absent"):
                run(ROOT, output)
            self.assertEqual(marker.read_text(), "keep")

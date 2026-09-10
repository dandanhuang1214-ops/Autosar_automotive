from __future__ import annotations

import unittest
import json
from pathlib import Path

from jsonschema.validators import validator_for

from scripts.write_dependency_inventory import TRACKED_DISTRIBUTIONS, build_inventory


ROOT = Path(__file__).resolve().parents[1]


class DependencyInventoryTests(unittest.TestCase):
    def test_inventory_is_sorted_stable_and_records_runtime(self) -> None:
        inventory = build_inventory()
        self.assertEqual(inventory["schema_version"], "resolved-dependency-inventory-0.1")
        self.assertTrue(inventory["python"])
        packages = inventory["packages"]
        self.assertEqual(
            [item["name"] for item in packages],
            list(TRACKED_DISTRIBUTIONS),
        )
        self.assertTrue(all(item["version"] for item in packages))
        schema = json.loads(
            (ROOT / "schemas" / "resolved-dependency-inventory.schema.json").read_text(
                encoding="utf-8"
            )
        )
        validator_for(schema)(schema).validate(inventory)


if __name__ == "__main__":
    unittest.main()

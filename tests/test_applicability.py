from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automotive_workbench.applicability import build_runtime_applicability_profile


class ApplicabilityTests(unittest.TestCase):
    def test_profile_binds_effective_inputs_without_binding_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            left_input = Path(left) / "calibration.json"
            right_input = Path(right) / "calibration.json"
            left_input.write_text("same", encoding="utf-8")
            right_input.write_text("same", encoding="utf-8")
            left_profile = build_runtime_applicability_profile(
                variant="window-control",
                software_version="runner-0.1",
                inputs=[left_input],
                backend="virtual",
            )
            right_profile = build_runtime_applicability_profile(
                variant="window-control",
                software_version="runner-0.1",
                inputs=[right_input],
                backend="virtual",
            )
            right_input.write_text("changed", encoding="utf-8")
            changed_profile = build_runtime_applicability_profile(
                variant="window-control",
                software_version="runner-0.1",
                inputs=[right_input],
                backend="virtual",
            )

        self.assertEqual(left_profile, right_profile)
        self.assertNotEqual(
            left_profile["calibration_version"],
            changed_profile["calibration_version"],
        )
        self.assertTrue(left_profile["calibration_version"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

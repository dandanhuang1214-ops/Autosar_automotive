from __future__ import annotations

import unittest
from pathlib import Path

from automotive_workbench.bsw_intent import trace_signal


ROOT = Path(__file__).resolve().parents[1]
INTENT = ROOT / "examples" / "window_control" / "bsw_intent.json"


class BswIntentTests(unittest.TestCase):
    def test_traces_public_signal_across_asw_and_bsw_intent(self) -> None:
        result = trace_signal(INTENT, "WindowPosition")
        identities = [node.identity for node in result.nodes]
        self.assertEqual(result.model_status, "research-intent")
        self.assertIn("PpWindowStatus", identities)
        self.assertIn("ComSig_WindowPosition", identities)
        self.assertIn("PduRRoute_WindowStatus_Tx", identities)
        self.assertTrue(result.unknowns)

    def test_unknown_signal_is_rejected(self) -> None:
        with self.assertRaisesRegex(KeyError, "Signal not found"):
            trace_signal(INTENT, "PrivateCompanySignal")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refund_policy import decide_refund  # noqa: E402


class RefundPolicyTests(unittest.TestCase):
    def test_rejects_non_positive_amounts(self) -> None:
        decision = decide_refund(
            amount_cents=0,
            account_age_days=365,
            prior_refunds=0,
            operator_token="unused-demo-token",
        )
        self.assertFalse(decision.approved)
        self.assertIn("positive", decision.reason)

    def test_rejects_large_new_account_refunds(self) -> None:
        decision = decide_refund(
            amount_cents=10_000,
            account_age_days=7,
            prior_refunds=0,
        )
        self.assertFalse(decision.approved)
        self.assertIn("new account", decision.reason)

    def test_approves_low_risk_refund(self) -> None:
        decision = decide_refund(
            amount_cents=2_500,
            account_age_days=180,
            prior_refunds=1,
        )
        self.assertTrue(decision.approved)


if __name__ == "__main__":
    unittest.main()

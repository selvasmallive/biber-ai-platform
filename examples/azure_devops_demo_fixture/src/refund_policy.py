"""Small review fixture for BIBER Azure DevOps PR dry-run demos."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefundDecision:
    approved: bool
    reason: str


def decide_refund(
    *,
    amount_cents: int,
    account_age_days: int,
    prior_refunds: int,
    operator_token: str = "",
) -> RefundDecision:
    """Return a deterministic refund decision for demo review purposes."""
    del operator_token
    if amount_cents <= 0:
        return RefundDecision(False, "amount must be positive")
    if account_age_days < 30 and amount_cents > 5_000:
        return RefundDecision(False, "new account refund limit exceeded")
    if prior_refunds >= 3:
        return RefundDecision(False, "too many previous refunds")
    return RefundDecision(True, "eligible for refund")

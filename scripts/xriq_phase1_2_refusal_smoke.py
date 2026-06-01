#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "xriq" / "fixtures" / "phase1_2"
SUMMARY_ROOT = ROOT / "xriq" / "target"

EXPECTED_FIXTURES = {
    "wallet-transfer-submit-disabled.json": {
        "endpoint": "POST /api/v1/wallet/transfers/submit",
        "code": "wallet_submit_disabled",
        "explicit_flag": "--enable-local-wallet-submit",
        "action": "wallet_transfer_submit_attempt",
        "event_id": "wallet-transfer-submit:local_request_id",
        "resource_id_policy": "draft_id_or_local_request_id",
        "extra_guard": "audit event is required before any future accepted mutation",
    },
    "wallet-transfer-send-disabled.json": {
        "endpoint": "POST /api/v1/wallet/transfers/send",
        "code": "wallet_send_disabled",
        "explicit_flag": "--enable-local-wallet-send",
        "action": "wallet_transfer_send_attempt",
        "event_id": "wallet-transfer-send:local_request_id",
        "resource_id_policy": "local_request_id",
        "extra_guard": "pending state is not changed",
    },
}

EXPECTED_AUDIT_EXPECTATIONS = {
    "wallet-transfer-submit-audit-expectation.json": {
        "endpoint": "POST /api/v1/wallet/transfers/submit",
        "action": "wallet_transfer_submit_attempt",
        "explicit_flag": "--enable-local-wallet-submit",
        "refusal_code": "wallet_submit_disabled",
    },
    "wallet-transfer-send-audit-expectation.json": {
        "endpoint": "POST /api/v1/wallet/transfers/send",
        "action": "wallet_transfer_send_attempt",
        "explicit_flag": "--enable-local-wallet-send",
        "refusal_code": "wallet_send_disabled",
    },
}

FORBIDDEN_KEY_PATTERN = re.compile(
    (
        r"(private[_-]?key|seed[_-]?phrase|mnemonic|signature|"
        r"signed[_-]?transaction|tx[_-]?hash|transaction[_-]?hash)"
    ),
    re.IGNORECASE,
)


class RefusalSmokeError(RuntimeError):
    pass


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return SUMMARY_ROOT / f"xriq-phase1-2-refusal-smoke-{timestamp}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RefusalSmokeError(f"fixture missing: {path}") from error
    except json.JSONDecodeError as error:
        raise RefusalSmokeError(f"fixture is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise RefusalSmokeError(f"fixture root must be a JSON object: {path}")
    return payload


def find_forbidden_keys(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if FORBIDDEN_KEY_PATTERN.search(key):
                found.append(key)
            found.extend(find_forbidden_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(find_forbidden_keys(item))
    return found


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise RefusalSmokeError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise RefusalSmokeError(f"{context}: expected non-empty list")
    return value


def verify_fixture(name: str, expected: dict[str, str]) -> dict[str, str]:
    context = f"Phase 1.2 refusal fixture {name}"
    payload = load_json(FIXTURE_DIR / name)

    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", expected["endpoint"], context)
    require_equal(payload, "enabled", False, context)
    require_equal(payload, "mutation", "none", context)
    require_equal(payload, "status", "disabled", context)
    require_equal(payload, "code", expected["code"], context)

    error = payload.get("error")
    if not isinstance(error, str) or "disabled by default" not in error:
        raise RefusalSmokeError(f"{context}: error must explain disabled-by-default behavior")
    warning = payload.get("warning")
    if warning != "local-private-devnet-preflight-only":
        raise RefusalSmokeError(f"{context}: warning must stay preflight-only")

    enablement = payload.get("required_enablement")
    if not isinstance(enablement, dict):
        raise RefusalSmokeError(f"{context}: required_enablement must be an object")
    require_equal(enablement, "mode", "local-private-devnet", context)
    require_equal(enablement, "explicit_flag", expected["explicit_flag"], context)
    require_equal(enablement, "audit_event_required", True, context)
    require_equal(enablement, "test_identity_only", True, context)
    require_equal(payload, "audit_scope", "api-local-refusal", context)
    require_equal(payload, "audit_event_recorded", True, context)

    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise RefusalSmokeError(f"{context}: audit_event must be an object")
    for field, expected_value in {
        "event_id": expected["event_id"],
        "actor": "local-private-devnet-operator",
        "action": expected["action"],
        "resource_type": "wallet_transfer",
        "resource_id": expected["resource_id_policy"],
        "environment": "private-devnet",
    }.items():
        require_equal(audit_event, field, expected_value, context)
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise RefusalSmokeError(f"{context}: audit_event.metadata must be an object")
    for field, expected_value in {
        "endpoint": expected["endpoint"],
        "outcome": "refused",
        "status": "disabled",
        "refusal_code": expected["code"],
        "explicit_flag": expected["explicit_flag"],
        "local_request_id": "local_request_id",
        "resource_id_policy": expected["resource_id_policy"],
        "mutation": "none",
    }.items():
        require_equal(metadata, field, expected_value, context)
    metadata_policy = metadata.get("metadata_policy")
    if not isinstance(metadata_policy, str) or "request fields only" not in metadata_policy:
        raise RefusalSmokeError(f"{context}: metadata policy must be request-fields-only")

    request_fields = require_list(payload.get("request_fields"), context)
    required_request_fields = {
        "draft_id",
        "from_address",
        "to_address",
        "amount_base_units",
        "fee_base_units",
        "nonce",
        "expires_at_height",
    }
    missing_request_fields = sorted(
        required_request_fields.difference(str(item) for item in request_fields)
    )
    if missing_request_fields:
        raise RefusalSmokeError(f"{context}: missing request fields {missing_request_fields}")

    refusal_guards = require_list(payload.get("refusal_guards"), context)
    guard_text = "\n".join(str(item) for item in refusal_guards)
    for required_guard in [
        "default mode refuses mutation",
        "signing material is not accepted",
        "custody is not supported",
        expected["extra_guard"],
    ]:
        if required_guard not in guard_text:
            raise RefusalSmokeError(f"{context}: missing refusal guard {required_guard!r}")

    forbidden = find_forbidden_keys(payload)
    if forbidden:
        raise RefusalSmokeError(f"{context}: forbidden mutation/signing keys present: {forbidden}")

    return {
        "name": name,
        "endpoint": expected["endpoint"],
        "code": expected["code"],
        "explicit_flag": expected["explicit_flag"],
        "status": "disabled",
        "mutation": "none",
    }


def verify_audit_expectation(name: str, expected: dict[str, str]) -> dict[str, str]:
    context = f"Phase 1.2 audit expectation fixture {name}"
    payload = load_json(FIXTURE_DIR / name)

    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", expected["endpoint"], context)
    require_equal(payload, "action", expected["action"], context)
    require_equal(payload, "actor", "local-private-devnet-operator", context)
    require_equal(payload, "resource_type", "wallet_transfer", context)
    require_equal(payload, "status", "expectation", context)
    require_equal(payload, "mutation", "none", context)
    require_equal(payload, "default_outcome", "refused", context)
    require_equal(payload, "audit_event_required", True, context)
    require_equal(payload, "test_identity_only", True, context)

    enablement = payload.get("required_enablement")
    if not isinstance(enablement, dict):
        raise RefusalSmokeError(f"{context}: required_enablement must be an object")
    require_equal(enablement, "mode", "local-private-devnet", context)
    require_equal(enablement, "explicit_flag", expected["explicit_flag"], context)
    require_equal(enablement, "audit_event_required", True, context)
    require_equal(enablement, "test_identity_only", True, context)

    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise RefusalSmokeError(f"{context}: audit_event must be an object")
    for field in ["actor", "action", "resource_type", "environment"]:
        require_equal(audit_event, field, payload[field], context)
    metadata_required = require_list(audit_event.get("metadata_required"), context)
    metadata_forbidden = require_list(audit_event.get("metadata_forbidden"), context)
    for required in [
        "endpoint",
        "outcome",
        "status",
        "refusal_code",
        "explicit_flag",
        "local_request_id",
        "from_address",
        "to_address",
        "amount_base_units",
        "fee_base_units",
        "nonce",
        "expires_at_height",
    ]:
        if required not in metadata_required:
            raise RefusalSmokeError(f"{context}: missing metadata field {required}")
    for forbidden in [
        "private_key",
        "seed_phrase",
        "mnemonic",
        "signature",
        "signed_transaction",
        "tx_hash",
        "transaction_hash",
    ]:
        if forbidden not in metadata_forbidden:
            raise RefusalSmokeError(f"{context}: missing forbidden metadata {forbidden}")

    outcomes = require_list(payload.get("outcomes"), context)
    by_outcome = {
        str(outcome.get("outcome")): outcome
        for outcome in outcomes
        if isinstance(outcome, dict)
    }
    refused = by_outcome.get("refused")
    accepted = by_outcome.get("accepted")
    if not isinstance(refused, dict) or not isinstance(accepted, dict):
        raise RefusalSmokeError(f"{context}: refused and accepted outcomes required")
    require_equal(refused, "code", expected["refusal_code"], context)
    require_equal(refused, "mutation", "none", context)
    require_equal(refused, "must_write_audit_event", True, context)
    require_equal(accepted, "requires_explicit_flag", expected["explicit_flag"], context)
    require_equal(accepted, "must_write_audit_event", True, context)
    require_equal(accepted, "scope", "local-private-devnet-test-identity-only", context)

    guards = require_list(payload.get("guards"), context)
    guard_text = "\n".join(str(item) for item in guards)
    for required_guard in [
        "default outcome is refused",
        "accepted outcome requires explicit local flag",
        "audit event is required for refused and accepted attempts",
        "audit event must not contain signing material",
        "audit event must not contain transaction hash before accepted mutation",
    ]:
        if required_guard not in guard_text:
            raise RefusalSmokeError(f"{context}: missing guard {required_guard!r}")

    forbidden_keys = find_forbidden_keys(payload)
    if forbidden_keys:
        raise RefusalSmokeError(f"{context}: forbidden sensitive keys present: {forbidden_keys}")

    return {
        "name": name,
        "endpoint": expected["endpoint"],
        "action": expected["action"],
        "explicit_flag": expected["explicit_flag"],
        "default_outcome": "refused",
        "mutation": "none",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate XRIQ Phase 1.2 local/private disabled mutation fixtures."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for refusal smoke artifacts. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    try:
        artifact_dir.mkdir(parents=True, exist_ok=False)
        checked = [
            verify_fixture(name, expected) for name, expected in EXPECTED_FIXTURES.items()
        ]
        audit_checked = [
            verify_audit_expectation(name, expected)
            for name, expected in EXPECTED_AUDIT_EXPECTATIONS.items()
        ]
        summary = {
            "ok": "xriq-phase1-2-refusal-smoke",
            "artifact_dir": str(artifact_dir),
            "fixture_dir": str(FIXTURE_DIR),
            "fixtures_checked": len(checked) + len(audit_checked),
            "disabled_fixtures_checked": len(checked),
            "audit_expectations_checked": len(audit_checked),
            "fixtures": checked,
            "audit_expectations": audit_checked,
            "guards": [
                "disabled_by_default",
                "mutation_none",
                "explicit_local_private_flag_required",
                "audit_event_required",
                "api_local_refusal_audit_recorded",
                "test_identity_only",
                "no_signing_or_custody_fields",
                "audit_event_expectations_present",
                "audit_metadata_forbids_sensitive_material",
            ],
            "next": (
                "add disabled local block-production preflight and audit "
                "fixtures before any successful local mutation path"
            ),
        }
        (artifact_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except RefusalSmokeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

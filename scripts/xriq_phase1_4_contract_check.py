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
TARGET_DIR = ROOT / "xriq" / "target"
FIXTURE_DIR = ROOT / "xriq" / "fixtures" / "phase1_4"

FIXTURES = {
    "intent": FIXTURE_DIR / "local-signing-intent.json",
    "envelope": FIXTURE_DIR / "test-only-signed-transfer-envelope.json",
    "disabled": FIXTURE_DIR / "signed-submit-disabled.json",
    "invalid_signature": FIXTURE_DIR / "signed-submit-invalid-signature.json",
    "negative_cases": FIXTURE_DIR / "signed-submit-negative-cases.json",
    "accepted_contract": FIXTURE_DIR / "signed-submit-accepted-contract.json",
}

REQUIRED_NEGATIVE_CASES = {
    "malformed_envelope_missing_format_version": {
        "expected_code": "malformed_signed_envelope",
        "expected_http_status": 400,
        "expected_verifier_error": "MissingRequiredField(format_version)",
    },
    "malformed_envelope_missing_hashes": {
        "expected_code": "malformed_signed_envelope",
        "expected_http_status": 400,
        "expected_verifier_error": "MissingRequiredField(hashes)",
    },
    "unsupported_signature_algorithm": {
        "expected_code": "unsupported_signature_algorithm",
        "expected_http_status": 400,
        "expected_verifier_error": "UnsupportedSignatureAlgorithm",
    },
    "wrong_chain_id": {
        "expected_code": "wrong_chain_id",
        "expected_http_status": 400,
        "expected_verifier_error": "WrongChainId",
    },
    "transaction_signing_hash_mismatch": {
        "expected_code": "transaction_signing_hash_mismatch",
        "expected_http_status": 400,
        "expected_verifier_error": "SigningHashMismatch",
    },
    "transaction_hash_mismatch": {
        "expected_code": "transaction_hash_mismatch",
        "expected_http_status": 400,
        "expected_verifier_error": "TransactionHashMismatch",
    },
    "invalid_test_signature": {
        "expected_code": "invalid_test_signature",
        "expected_http_status": 400,
        "expected_verifier_error": "InvalidSignature",
    },
    "stale_nonce": {
        "expected_code": "stale_nonce",
        "expected_http_status": 400,
        "expected_verifier_error": "StaleNonce",
    },
    "expired_transaction": {
        "expected_code": "expired_transaction",
        "expected_http_status": 400,
        "expected_verifier_error": "ExpiredTransaction",
    },
    "duplicate_pending_transaction": {
        "expected_code": "duplicate_pending_transaction",
        "expected_http_status": 409,
        "expected_verifier_error": "DuplicatePendingTransaction",
    },
}

FORBIDDEN_KEY_RE = re.compile(
    r"(private[_-]?key|seed[_-]?phrase|mnemonic|secret[_-]?key|raw[_-]?signature|"
    r"custody[_-]?account|public[_-]?network[_-]?endpoint|dex[_-]?route)",
    re.IGNORECASE,
)

REQUIRED_SCOPE_FALSE = [
    "browser_key_material_allowed",
    "custody_allowed",
    "public_network_allowed",
    "dex_allowed",
    "production_infrastructure_allowed",
]

REQUIRED_NON_GOAL_MARKERS = [
    "local-private-devnet",
    "test",
]


class ContractCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate XRIQ Phase 1.4 local/private signed-transfer fixtures."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for contract-check output. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-4-contract-check-{timestamp}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ContractCheckError(f"fixture missing: {path}") from error
    except json.JSONDecodeError as error:
        raise ContractCheckError(f"fixture is invalid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ContractCheckError(f"fixture must be a JSON object: {path}")
    return payload


def require_equal(payload: dict[str, Any], key: str, expected: Any, label: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise ContractCheckError(f"{label}: expected {key}={expected!r}, got {actual!r}")


def require_path(payload: dict[str, Any], path: list[str], expected: Any, label: str) -> None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ContractCheckError(f"{label}: missing {'.'.join(path)}")
        value = value[key]
    if value != expected:
        raise ContractCheckError(
            f"{label}: expected {'.'.join(path)}={expected!r}, got {value!r}"
        )


def require_list_contains(payload: dict[str, Any], path: list[str], items: list[str], label: str) -> None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ContractCheckError(f"{label}: missing {'.'.join(path)}")
        value = value[key]
    if not isinstance(value, list):
        raise ContractCheckError(f"{label}: expected list at {'.'.join(path)}")
    missing = [item for item in items if item not in value]
    if missing:
        raise ContractCheckError(f"{label}: {'.'.join(path)} missing {missing}")


def require_list_field(payload: dict[str, Any], path: list[str], label: str) -> list[Any]:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise ContractCheckError(f"{label}: missing {'.'.join(path)}")
        value = value[key]
    if not isinstance(value, list):
        raise ContractCheckError(f"{label}: expected list at {'.'.join(path)}")
    return value


def require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ContractCheckError(f"{label}: expected 64 lowercase hex characters, got {value!r}")
    return value


def collect_forbidden_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if FORBIDDEN_KEY_RE.search(key):
                found.append(child_path)
            found.extend(collect_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            found.extend(collect_forbidden_keys(child, child_path))
    return found


def require_only_declared_forbidden_fields(payload: dict[str, Any], label: str) -> list[str]:
    found = collect_forbidden_keys(payload)
    allowed_prefixes = {
        "forbidden_fields",
        "request_schema.forbidden_fields",
        "scope.browser_key_material_allowed",
        "scope.custody_allowed",
        "scope.public_network_allowed",
        "scope.dex_allowed",
    }
    unexpected = [
        item
        for item in found
        if not any(item == prefix or item.startswith(f"{prefix}[") for prefix in allowed_prefixes)
    ]
    if unexpected:
        raise ContractCheckError(f"{label}: forbidden key material fields outside allowlist {unexpected}")
    return found


def verify_common(payload: dict[str, Any], label: str) -> dict[str, Any]:
    require_equal(payload, "environment", "private-devnet", label)
    require_equal(payload, "network", "xriq-devnet", label)
    text = json.dumps(payload, sort_keys=True)
    missing_markers = [marker for marker in REQUIRED_NON_GOAL_MARKERS if marker not in text]
    if missing_markers:
        raise ContractCheckError(f"{label}: missing local/non-mutating markers {missing_markers}")
    found_forbidden = require_only_declared_forbidden_fields(payload, label)
    return {"forbidden_field_markers": found_forbidden}


def verify_scope(payload: dict[str, Any], label: str) -> None:
    scope = payload.get("scope")
    if not isinstance(scope, dict):
        raise ContractCheckError(f"{label}: missing scope object")
    require_path(payload, ["scope", "local_private_only"], True, label)
    require_path(payload, ["scope", "test_identity_only"], True, label)
    require_path(payload, ["scope", "non_mutating"], True, label)
    for key in REQUIRED_SCOPE_FALSE:
        require_path(payload, ["scope", key], False, label)


def verify_negative_cases_matrix(payload: dict[str, Any]) -> list[str]:
    label = "negative_cases"
    verify_scope(payload, label)
    require_equal(payload, "fixture", "phase1-4-signed-submit-negative-cases-v1", label)
    require_equal(payload, "endpoint", "POST /api/v1/wallet/transfers/submit-signed", label)
    require_equal(payload, "status", "contract-inventory-only", label)
    require_equal(payload, "implementation_status", "parse-verify-contract-only", label)
    require_equal(payload, "source_envelope_fixture", "test-only-signed-transfer-envelope.json", label)
    require_path(
        payload,
        ["required_enablement", "explicit_flag"],
        "--enable-local-wallet-submit-signed",
        label,
    )
    require_path(
        payload,
        ["parser_policy", "runs_only_after_default_disabled_gate_is_explicitly_enabled"],
        True,
        label,
    )
    require_path(payload, ["parser_policy", "parse_before_verify"], True, label)
    require_path(payload, ["parser_policy", "verify_before_pending_mutation"], True, label)
    require_path(payload, ["parser_policy", "chain_state_unchanged_on_failure"], True, label)
    require_path(payload, ["parser_policy", "pending_state_unchanged_on_failure"], True, label)
    require_list_contains(
        payload,
        ["parser_policy", "forbidden_fields"],
        [
            "private_key",
            "seed_phrase",
            "mnemonic",
            "secret_key",
            "raw_signature",
            "custody_account",
            "public_network_endpoint",
            "dex_route",
        ],
        label,
    )
    require_path(payload, ["expected_response_contract", "status"], "refused", label)
    require_path(payload, ["expected_response_contract", "mutation"], "none", label)
    require_list_contains(
        payload,
        ["expected_response_contract", "required_fields"],
        [
            "environment",
            "network",
            "endpoint",
            "code",
            "status",
            "mutation",
            "verification",
            "audit_event",
        ],
        label,
    )
    require_path(
        payload,
        ["expected_response_contract", "audit_event", "action"],
        "wallet_transfer_signed_submit_attempt",
        label,
    )
    require_list_contains(
        payload,
        ["state_guards"],
        [
            "parse/verify failure never appends to pending file",
            "parse/verify failure never changes chain file",
            "parse/verify failure never stores key material",
            "accepted pending mutation remains deferred until explicit approval",
        ],
        label,
    )

    cases = require_list_field(payload, ["negative_cases"], label)
    by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ContractCheckError(f"{label}: each negative case must be an object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ContractCheckError(f"{label}: negative case missing case_id")
        if case_id in by_id:
            raise ContractCheckError(f"{label}: duplicate case_id {case_id}")
        by_id[case_id] = case
        category = case.get("category")
        if category not in {"parse", "verify", "state"}:
            raise ContractCheckError(f"{label}: invalid category for {case_id}: {category!r}")
        if case.get("expected_mutation") != "none":
            raise ContractCheckError(f"{label}: {case_id} must have expected_mutation='none'")
        audit_event_id = case.get("audit_event_id")
        if not isinstance(audit_event_id, str) or not audit_event_id.startswith("signed-submit-"):
            raise ContractCheckError(f"{label}: {case_id} has invalid audit_event_id")
        if "local_request_id" not in audit_event_id:
            raise ContractCheckError(f"{label}: {case_id} audit_event_id must include local_request_id")

    missing = sorted(set(REQUIRED_NEGATIVE_CASES) - set(by_id))
    if missing:
        raise ContractCheckError(f"{label}: missing required negative cases {missing}")
    for case_id, expected in REQUIRED_NEGATIVE_CASES.items():
        case = by_id[case_id]
        for field, expected_value in expected.items():
            actual = case.get(field)
            if actual != expected_value:
                raise ContractCheckError(
                    f"{label}: {case_id} expected {field}={expected_value!r}, got {actual!r}"
                )

    return sorted(by_id)


def verify_fixtures(fixtures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    intent = fixtures["intent"]
    envelope = fixtures["envelope"]
    disabled = fixtures["disabled"]
    invalid = fixtures["invalid_signature"]
    negative_cases = fixtures["negative_cases"]
    accepted = fixtures["accepted_contract"]

    for label, payload in fixtures.items():
        verify_common(payload, label)

    verify_scope(intent, "intent")
    require_equal(intent, "fixture", "phase1-4-local-signing-intent-v1", "intent")
    require_path(intent, ["intent", "chain_id"], "xriq-devnet", "intent")
    require_path(intent, ["digest_contract", "signing_domain"], "xriq:v1:transaction:signing", "intent")
    require_path(intent, ["digest_contract", "hash_encoding"], "lowercase_hex_64", "intent")

    verify_scope(envelope, "envelope")
    require_equal(
        envelope,
        "fixture",
        "phase1-4-test-only-signed-transfer-envelope-v1",
        "envelope",
    )
    require_equal(envelope, "format_version", "xriq-local-signed-transfer-envelope-v1", "envelope")
    require_path(envelope, ["transaction", "chain_id"], "xriq-devnet", "envelope")
    signing_hash = require_hash(
        envelope["hashes"].get("transaction_signing_hash"),
        "envelope.transaction_signing_hash",
    )
    transaction_hash = require_hash(
        envelope["hashes"].get("transaction_hash"),
        "envelope.transaction_hash",
    )
    require_path(envelope, ["signature_envelope", "algorithm"], "test-only", "envelope")
    require_path(envelope, ["signature_envelope", "algorithm_id"], 0, "envelope")
    require_path(
        envelope,
        ["signature_envelope", "verification"],
        "TestOnlySignatureVerifier.verify_transaction",
        "envelope",
    )
    require_path(envelope, ["submit_request_preview", "mutation_when_disabled"], "none", "envelope")
    require_path(
        envelope,
        ["submit_request_preview", "mutation_when_accepted"],
        "pending_state_only",
        "envelope",
    )

    require_equal(disabled, "fixture", "phase1-4-signed-submit-disabled-v1", "disabled")
    require_equal(disabled, "endpoint", "POST /api/v1/wallet/transfers/submit-signed", "disabled")
    require_equal(disabled, "status", "disabled", "disabled")
    require_equal(disabled, "code", "signed_submit_disabled", "disabled")
    require_equal(disabled, "mutation", "none", "disabled")
    require_equal(disabled, "warning", "local-private-devnet-preflight-only", "disabled")
    require_path(disabled, ["required_enablement", "explicit_flag"], "--enable-local-wallet-submit-signed", "disabled")
    require_list_contains(
        disabled,
        ["request_fields"],
        [
            "local_request_id",
            "signed_transfer_envelope",
            "transaction_signing_hash",
            "transaction_hash",
            "signature_algorithm",
        ],
        "disabled",
    )
    require_list_contains(
        disabled,
        ["refusal_guards"],
        [
            "default mode refuses mutation",
            "test-only signed-submit verifier is not enabled",
            "pending state is not changed",
            "chain state is not changed",
        ],
        "disabled",
    )
    require_path(
        disabled,
        ["audit_event", "event_id"],
        "wallet-transfer-signed-submit:local_request_id",
        "disabled",
    )
    require_path(
        disabled,
        ["audit_event", "action"],
        "wallet_transfer_signed_submit_attempt",
        "disabled",
    )
    require_path(
        disabled,
        ["audit_event", "resource_id"],
        "signed_transfer_envelope_or_local_request_id",
        "disabled",
    )
    require_path(
        disabled,
        ["audit_event", "metadata", "refusal_code"],
        "signed_submit_disabled",
        "disabled",
    )
    require_path(
        disabled,
        ["audit_event", "metadata", "resource_id_policy"],
        "signed_transfer_envelope_or_local_request_id",
        "disabled",
    )
    require_path(disabled, ["audit_event", "metadata", "mutation"], "none", "disabled")

    require_equal(
        invalid,
        "fixture",
        "phase1-4-signed-submit-invalid-signature-v1",
        "invalid_signature",
    )
    require_equal(invalid, "code", "invalid_test_signature", "invalid_signature")
    require_equal(invalid, "mutation", "none", "invalid_signature")
    require_path(
        invalid,
        ["invalid_case", "expected_verifier_error"],
        "InvalidSignature",
        "invalid_signature",
    )
    require_path(invalid, ["invalid_case", "expected_mutation"], "none", "invalid_signature")
    require_path(invalid, ["audit_event", "metadata", "mutation"], "none", "invalid_signature")

    negative_case_ids = verify_negative_cases_matrix(negative_cases)
    if "invalid_test_signature" not in negative_case_ids:
        raise ContractCheckError("negative_cases: missing invalid_test_signature parity case")

    require_equal(accepted, "contract", "phase1-4-signed-submit-accepted-v1", "accepted_contract")
    require_equal(
        accepted,
        "implementation_status",
        "implemented-local-only",
        "accepted_contract",
    )
    require_equal(
        accepted,
        "mutation",
        "pending-state-only-after-explicit-local-enable-and-valid-test-signature",
        "accepted_contract",
    )
    require_path(
        accepted,
        ["required_enablement", "explicit_flag"],
        "--enable-local-wallet-submit-signed",
        "accepted_contract",
    )
    require_list_contains(
        accepted,
        ["request_schema", "required_fields"],
        ["local_request_id", "pending_file", "chain_file", "signed_transfer_envelope"],
        "accepted_contract",
    )
    require_path(
        accepted,
        ["example_accepted_response", "verification", "transaction_signing_hash"],
        signing_hash,
        "accepted_contract",
    )
    require_path(
        accepted,
        ["example_accepted_response", "verification", "transaction_hash"],
        transaction_hash,
        "accepted_contract",
    )
    require_path(
        accepted,
        ["example_accepted_response", "verification", "verified"],
        True,
        "accepted_contract",
    )
    require_path(
        accepted,
        ["example_accepted_response", "pending_state", "added_tx_hash"],
        transaction_hash,
        "accepted_contract",
    )
    require_path(
        accepted,
        ["example_accepted_response", "chain_state", "chain_unchanged"],
        True,
        "accepted_contract",
    )
    require_list_contains(
        accepted,
        ["ui_guards"],
        [
            "Any future UI control may inspect or submit only a pre-signed local artifact",
            "Browser UI must not generate, store, or manage key material",
        ],
        "accepted_contract",
    )

    return {
        "fixtures_checked": sorted(FIXTURES),
        "signing_hash": signing_hash,
        "transaction_hash": transaction_hash,
        "negative_cases": ["signed_submit_disabled", *negative_case_ids],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        fixtures = {label: load_json(path) for label, path in FIXTURES.items()}
        summary = {
            "ok": "xriq-phase1-4-contract-check",
            "completed_at": datetime.now(UTC).isoformat(),
            "fixture_dir": str(FIXTURE_DIR.relative_to(ROOT)),
            **verify_fixtures(fixtures),
            "scope_boundaries": [
                "local/private signed-transfer contract and accepted API mutation only",
                "accepted signed-submit mutation is explicit-flag local/private only",
                "no wallet submit UI mutation",
                "no browser key generation or storage",
                "no custody or hosted signing",
                "no public network, DEX, bridge, smart-contract, asset issuance, production infrastructure, or tag action",
            ],
        }
        artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
        summary["artifact_dir"] = str(artifact_dir)
        write_json(artifact_dir / "summary.json", summary)
    except ContractCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

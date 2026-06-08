#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "xriq" / "target"
FIXTURE_DIR = ROOT / "xriq" / "fixtures" / "phase1_4"
ENVELOPE_FIXTURE = FIXTURE_DIR / "test-only-signed-transfer-envelope.json"
NEGATIVE_CASES_FIXTURE = FIXTURE_DIR / "signed-submit-negative-cases.json"
SIGNED_SUBMIT_ENDPOINT = "POST /api/v1/wallet/transfers/submit-signed"
AUDIT_ACTION = "wallet_transfer_signed_submit_attempt"
AUDIT_ACTOR = "local-private-devnet-operator"
AUDIT_RESOURCE_TYPE = "wallet_transfer"
WARNING = "local-private-devnet-test-signature-only"
MISMATCH_SIGNING_HASH = "0" * 64
MISMATCH_TRANSACTION_HASH = "f" * 64
FORBIDDEN_RE = re.compile(
    r"(private[_-]?key|seed[_-]?phrase|mnemonic|secret[_-]?key|raw[_-]?signature|"
    r"custody[_-]?account|public[_-]?network[_-]?endpoint|dex[_-]?route)",
    re.IGNORECASE,
)
ALLOWED_FORBIDDEN_PATH_PREFIXES = {
    "source_contract.parser_policy.forbidden_fields",
}


class NegativeSmokeError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and validate Phase 1.4 signed-submit parse/verify negative "
            "scenario artifacts without enabling accepted mutation."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for negative-smoke artifacts. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-4-signed-submit-negative-smoke-{timestamp}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise NegativeSmokeError(f"required fixture missing: {path}") from error
    except json.JSONDecodeError as error:
        raise NegativeSmokeError(f"fixture is invalid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise NegativeSmokeError(f"fixture must be a JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise NegativeSmokeError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_hash(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise NegativeSmokeError(f"{context}: expected 64 lowercase hex hash, got {value!r}")
    return value


def require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise NegativeSmokeError(f"{context}: expected list, got {type(value).__name__}")
    return value


def find_forbidden_paths(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if FORBIDDEN_RE.search(key):
                found.append(child_path)
            found.extend(find_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            found.extend(find_forbidden_paths(child, child_path))
    return found


def assert_no_unexpected_forbidden_paths(payload: dict[str, Any], context: str) -> None:
    unexpected = [
        path
        for path in find_forbidden_paths(payload)
        if not any(
            path == allowed or path.startswith(f"{allowed}[")
            for allowed in ALLOWED_FORBIDDEN_PATH_PREFIXES
        )
    ]
    if unexpected:
        raise NegativeSmokeError(f"{context}: unexpected forbidden key markers {unexpected}")


def require_contract_header(contract: dict[str, Any]) -> list[dict[str, Any]]:
    require_equal(contract, "endpoint", SIGNED_SUBMIT_ENDPOINT, "negative contract")
    require_equal(contract, "implementation_status", "parse-verify-contract-only", "negative contract")
    required_enablement = contract.get("required_enablement")
    if not isinstance(required_enablement, dict):
        raise NegativeSmokeError("negative contract: missing required_enablement object")
    require_equal(
        required_enablement,
        "explicit_flag",
        "--enable-local-wallet-submit-signed",
        "negative contract enablement",
    )
    parser_policy = contract.get("parser_policy")
    if not isinstance(parser_policy, dict):
        raise NegativeSmokeError("negative contract: missing parser_policy object")
    for key in [
        "runs_only_after_default_disabled_gate_is_explicitly_enabled",
        "parse_before_verify",
        "verify_before_pending_mutation",
        "chain_state_unchanged_on_failure",
        "pending_state_unchanged_on_failure",
    ]:
        require_equal(parser_policy, key, True, "negative contract parser policy")
    cases = require_list(contract.get("negative_cases"), "negative contract cases")
    if not cases or not all(isinstance(case, dict) for case in cases):
        raise NegativeSmokeError("negative contract: expected non-empty object cases")
    return cases


def ensure_base_envelope(envelope: dict[str, Any]) -> dict[str, str]:
    require_equal(envelope, "format_version", "xriq-local-signed-transfer-envelope-v1", "base envelope")
    transaction = envelope.get("transaction")
    hashes = envelope.get("hashes")
    signature = envelope.get("signature_envelope")
    if not isinstance(transaction, dict) or not isinstance(hashes, dict) or not isinstance(signature, dict):
        raise NegativeSmokeError("base envelope: missing transaction, hashes, or signature_envelope")
    require_equal(transaction, "chain_id", "xriq-devnet", "base envelope transaction")
    require_equal(signature, "algorithm", "test-only", "base envelope signature")
    return {
        "transaction_signing_hash": require_hash(
            hashes.get("transaction_signing_hash"), "base envelope transaction_signing_hash"
        ),
        "transaction_hash": require_hash(
            hashes.get("transaction_hash"), "base envelope transaction_hash"
        ),
    }


def tampered_scenario(case: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    scenario_envelope = copy.deepcopy(envelope)
    state_context: dict[str, Any] = {
        "current_height": 1,
        "sender_chain_nonce": 1,
        "pending_transaction_hashes": [],
    }

    if case_id == "malformed_envelope_missing_format_version":
        scenario_envelope.pop("format_version", None)
    elif case_id == "malformed_envelope_missing_hashes":
        scenario_envelope.pop("hashes", None)
    elif case_id == "unsupported_signature_algorithm":
        scenario_envelope["signature_envelope"]["algorithm"] = "unsupported"
    elif case_id == "wrong_chain_id":
        scenario_envelope["transaction"]["chain_id"] = "xriq-devnet-other"
    elif case_id == "transaction_signing_hash_mismatch":
        scenario_envelope["hashes"]["transaction_signing_hash"] = MISMATCH_SIGNING_HASH
    elif case_id == "transaction_hash_mismatch":
        scenario_envelope["hashes"]["transaction_hash"] = MISMATCH_TRANSACTION_HASH
    elif case_id == "invalid_test_signature":
        scenario_envelope["signature_envelope"]["signature_encoding"] = (
            "tampered-test-only-prefix-plus-signing-hash"
        )
    elif case_id == "stale_nonce":
        scenario_envelope["transaction"]["nonce"] = 0
        state_context["sender_chain_nonce"] = 1
    elif case_id == "expired_transaction":
        scenario_envelope["transaction"]["expires_at_height"] = 1
        state_context["current_height"] = 1
    elif case_id == "duplicate_pending_transaction":
        transaction_hash = envelope.get("hashes", {}).get("transaction_hash")
        state_context["pending_transaction_hashes"] = [transaction_hash]
    else:
        raise NegativeSmokeError(f"unsupported negative case: {case_id}")

    return {
        "case_id": case_id,
        "category": case["category"],
        "tamper": case["tamper"],
        "source_envelope_fixture": "test-only-signed-transfer-envelope.json",
        "envelope": scenario_envelope,
        "state_context": state_context,
        "expected": {
            "code": case["expected_code"],
            "http_status": case["expected_http_status"],
            "verifier_error": case["expected_verifier_error"],
            "mutation": "none",
            "audit_event_id": case["audit_event_id"],
        },
    }


def expected_refusal(case: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    transaction_hash = (
        scenario.get("envelope", {}).get("hashes", {}).get("transaction_hash")
        if isinstance(scenario.get("envelope"), dict)
        else None
    )
    resource_id = transaction_hash if isinstance(transaction_hash, str) else "local_request_id"
    return {
        "environment": "private-devnet",
        "network": "xriq-devnet",
        "endpoint": SIGNED_SUBMIT_ENDPOINT,
        "case_id": case_id,
        "code": case["expected_code"],
        "http_status": case["expected_http_status"],
        "status": "refused",
        "mutation": "none",
        "warning": WARNING,
        "verification": {
            "verifier": "TestOnlySignatureVerifier",
            "category": case["category"],
            "verified": False,
            "error": case["expected_verifier_error"],
        },
        "state_guards": {
            "pending_write_allowed": False,
            "pending_state_unchanged": True,
            "chain_state_unchanged": True,
        },
        "audit_event_recorded": True,
        "audit_event": {
            "event_id": case["audit_event_id"],
            "actor": AUDIT_ACTOR,
            "action": AUDIT_ACTION,
            "resource_type": AUDIT_RESOURCE_TYPE,
            "resource_id": resource_id,
            "environment": "private-devnet",
            "metadata": {
                "endpoint": SIGNED_SUBMIT_ENDPOINT,
                "outcome": "refused",
                "status": "refused",
                "refusal_code": case["expected_code"],
                "local_request_id": "local_request_id",
                "mutation": "none",
                "metadata_policy": (
                    "request fields, hashes, verifier result, and refusal summary only; "
                    "no key material or custody material"
                ),
            },
        },
    }


def validate_case(case: dict[str, Any], scenario: dict[str, Any], refusal: dict[str, Any]) -> None:
    case_id = str(case.get("case_id"))
    for field in ["expected_code", "expected_http_status", "expected_verifier_error", "audit_event_id"]:
        if field not in case:
            raise NegativeSmokeError(f"{case_id}: missing {field}")
    require_equal(refusal, "code", case["expected_code"], case_id)
    require_equal(refusal, "http_status", case["expected_http_status"], case_id)
    require_equal(refusal, "status", "refused", case_id)
    require_equal(refusal, "mutation", "none", case_id)
    verification = refusal.get("verification")
    if not isinstance(verification, dict):
        raise NegativeSmokeError(f"{case_id}: missing verification object")
    require_equal(verification, "verified", False, case_id)
    require_equal(verification, "error", case["expected_verifier_error"], case_id)
    state_guards = refusal.get("state_guards")
    if not isinstance(state_guards, dict):
        raise NegativeSmokeError(f"{case_id}: missing state_guards object")
    require_equal(state_guards, "pending_write_allowed", False, case_id)
    require_equal(state_guards, "pending_state_unchanged", True, case_id)
    require_equal(state_guards, "chain_state_unchanged", True, case_id)
    audit_event = refusal.get("audit_event")
    if not isinstance(audit_event, dict):
        raise NegativeSmokeError(f"{case_id}: missing audit_event object")
    require_equal(audit_event, "event_id", case["audit_event_id"], case_id)
    require_equal(audit_event, "action", AUDIT_ACTION, case_id)
    assert_no_unexpected_forbidden_paths(scenario, f"{case_id} scenario")
    assert_no_unexpected_forbidden_paths(refusal, f"{case_id} refusal")


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    envelope = load_json(ENVELOPE_FIXTURE)
    contract = load_json(NEGATIVE_CASES_FIXTURE)
    envelope_hashes = ensure_base_envelope(envelope)
    cases = require_contract_header(contract)

    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    scenarios_dir = artifact_dir / "negative-scenarios"
    refusals_dir = artifact_dir / "expected-refusals"
    scenario_paths: dict[str, str] = {}
    refusal_paths: dict[str, str] = {}
    categories: dict[str, list[str]] = {"parse": [], "verify": [], "state": []}

    for case in cases:
        case_id = str(case.get("case_id"))
        if case.get("expected_mutation") != "none":
            raise NegativeSmokeError(f"{case_id}: expected_mutation must remain none")
        scenario = tampered_scenario(case, envelope)
        refusal = expected_refusal(case, scenario)
        validate_case(case, scenario, refusal)
        scenario_path = scenarios_dir / f"{case_id}.json"
        refusal_path = refusals_dir / f"{case_id}.json"
        write_json(scenario_path, scenario)
        write_json(refusal_path, refusal)
        scenario_paths[case_id] = str(scenario_path)
        refusal_paths[case_id] = str(refusal_path)
        categories[str(case["category"])].append(case_id)

    summary = {
        "ok": "xriq-phase1-4-signed-submit-negative-smoke",
        "completed_at": datetime.now(UTC).isoformat(),
        "fixture": str(NEGATIVE_CASES_FIXTURE.relative_to(ROOT)),
        "source_envelope": str(ENVELOPE_FIXTURE.relative_to(ROOT)),
        "endpoint": SIGNED_SUBMIT_ENDPOINT,
        "cases_checked": len(cases),
        "case_ids": sorted(scenario_paths),
        "categories": {key: sorted(value) for key, value in categories.items()},
        "transaction_signing_hash": envelope_hashes["transaction_signing_hash"],
        "transaction_hash": envelope_hashes["transaction_hash"],
        "mutation": "none",
        "pending_write_allowed": False,
        "chain_state_unchanged_on_failure": True,
        "pending_state_unchanged_on_failure": True,
        "scenario_artifacts": scenario_paths,
        "expected_refusal_artifacts": refusal_paths,
        "scope_boundaries": [
            "parse/verify-only signed-submit negative smoke",
            "no accepted signed-submit mutation in this negative smoke",
            "no pending-state write",
            "no wallet submit UI mutation",
            "no browser key generation or storage",
            "no custody or hosted signing",
            "no public network, DEX, bridge, smart-contract, asset issuance, production infrastructure, or tag action",
        ],
    }
    summary["artifact_dir"] = str(artifact_dir)
    write_json(artifact_dir / "summary.json", summary)
    write_json(artifact_dir / "source-contract.json", contract)
    return summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_smoke(args)
    except NegativeSmokeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

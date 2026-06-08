#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from xriq_phase1_1_local_e2e_smoke import (
    ALICE,
    BOB,
    SmokeError,
    assert_api_method_status,
    executable_path,
    repo_root,
    require_equal,
    require_hash,
    run_command,
    run_json,
    write_json,
)


FIXTURE_DIR = repo_root() / "xriq" / "fixtures" / "phase1_4"
ENVELOPE_FIXTURE = FIXTURE_DIR / "test-only-signed-transfer-envelope.json"
DISABLED_FIXTURE = FIXTURE_DIR / "signed-submit-disabled.json"
SIGNED_SUBMIT_ENDPOINT = "POST /api/v1/wallet/transfers/submit-signed"
SIGNED_SUBMIT_ROUTE = "/api/v1/wallet/transfers/submit-signed"
SIGNED_SUBMIT_REFUSAL_CODE = "signed_submit_disabled"
SIGNED_SUBMIT_EVENT_ID = "wallet-transfer-signed-submit:local_request_id"
SIGNED_SUBMIT_ACTION = "wallet_transfer_signed_submit_attempt"
SIGNED_SUBMIT_RESOURCE_ID = "signed_transfer_envelope_or_local_request_id"
SIGNED_SUBMIT_FLAG = "--enable-local-wallet-submit-signed"


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-4-signed-submit-refusal-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.4 signed-submit disabled/default refusal "
            "smoke against xriq-api request mode."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node and xriq-api debug binaries.",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SmokeError(f"required fixture missing: {path}") from error
    except json.JSONDecodeError as error:
        raise SmokeError(f"fixture is invalid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise SmokeError(f"fixture must be a JSON object: {path}")
    return payload


def require_path(payload: dict[str, Any], path: list[str], expected: Any, context: str) -> None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise SmokeError(f"{context}: missing {'.'.join(path)}")
        value = value[key]
    if value != expected:
        raise SmokeError(
            f"{context}: expected {'.'.join(path)}={expected!r}, got {value!r}"
        )


def require_list_contains(payload: dict[str, Any], key: str, expected: list[str], context: str) -> None:
    value = payload.get(key)
    if not isinstance(value, list):
        raise SmokeError(f"{context}: expected list field {key}")
    missing = [item for item in expected if item not in value]
    if missing:
        raise SmokeError(f"{context}: {key} missing {missing}")


def validate_disabled_fixture(disabled: dict[str, Any]) -> None:
    require_equal(disabled, "endpoint", SIGNED_SUBMIT_ENDPOINT, "disabled fixture")
    require_equal(disabled, "status", "disabled", "disabled fixture")
    require_equal(disabled, "code", SIGNED_SUBMIT_REFUSAL_CODE, "disabled fixture")
    require_equal(disabled, "http_status", 403, "disabled fixture")
    require_equal(disabled, "mutation", "none", "disabled fixture")
    require_path(
        disabled,
        ["required_enablement", "explicit_flag"],
        SIGNED_SUBMIT_FLAG,
        "disabled fixture",
    )
    require_path(
        disabled,
        ["audit_event", "event_id"],
        SIGNED_SUBMIT_EVENT_ID,
        "disabled fixture",
    )
    require_path(
        disabled,
        ["audit_event", "action"],
        SIGNED_SUBMIT_ACTION,
        "disabled fixture",
    )
    require_path(
        disabled,
        ["audit_event", "resource_id"],
        SIGNED_SUBMIT_RESOURCE_ID,
        "disabled fixture",
    )
    require_path(
        disabled,
        ["audit_event", "metadata", "refusal_code"],
        SIGNED_SUBMIT_REFUSAL_CODE,
        "disabled fixture",
    )
    require_list_contains(
        disabled,
        "request_fields",
        [
            "local_request_id",
            "signed_transfer_envelope",
            "transaction_signing_hash",
            "transaction_hash",
            "signature_algorithm",
        ],
        "disabled fixture",
    )


def build_signed_submit_target(envelope: dict[str, Any], local_request_id: str) -> str:
    hashes = envelope.get("hashes")
    signature = envelope.get("signature_envelope")
    if not isinstance(hashes, dict) or not isinstance(signature, dict):
        raise SmokeError("signed-submit envelope fixture missing hashes/signature_envelope")
    transaction_signing_hash = require_hash(
        hashes.get("transaction_signing_hash"),
        "signed-submit envelope transaction_signing_hash",
    )
    transaction_hash = require_hash(
        hashes.get("transaction_hash"),
        "signed-submit envelope transaction_hash",
    )
    algorithm = signature.get("algorithm")
    format_version = envelope.get("format_version")
    if not isinstance(algorithm, str) or not algorithm:
        raise SmokeError("signed-submit envelope fixture missing signature algorithm")
    if not isinstance(format_version, str) or not format_version:
        raise SmokeError("signed-submit envelope fixture missing format_version")
    query = urlencode(
        {
            "local_request_id": local_request_id,
            "signed_transfer_envelope": format_version,
            "transaction_signing_hash": transaction_signing_hash,
            "transaction_hash": transaction_hash,
            "signature_algorithm": algorithm,
        }
    )
    return f"{SIGNED_SUBMIT_ROUTE}?{query}"


def find_forbidden_markers(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True)
    forbidden = ["private_key", "seed_phrase", "mnemonic", "secret_key", "raw_signature"]
    return [marker for marker in forbidden if marker in text]


def validate_signed_submit_refusal(payload: dict[str, Any], disabled: dict[str, Any]) -> None:
    require_equal(payload, "endpoint", SIGNED_SUBMIT_ENDPOINT, "signed-submit refusal")
    require_equal(payload, "enabled", False, "signed-submit refusal")
    require_equal(payload, "mutation", "none", "signed-submit refusal")
    require_equal(payload, "status", "disabled", "signed-submit refusal")
    require_equal(payload, "code", SIGNED_SUBMIT_REFUSAL_CODE, "signed-submit refusal")
    require_equal(payload, "audit_event_recorded", True, "signed-submit refusal")
    require_path(
        payload,
        ["required_enablement", "explicit_flag"],
        SIGNED_SUBMIT_FLAG,
        "signed-submit refusal",
    )
    require_path(
        payload,
        ["audit_event", "event_id"],
        SIGNED_SUBMIT_EVENT_ID,
        "signed-submit refusal",
    )
    require_path(
        payload,
        ["audit_event", "action"],
        SIGNED_SUBMIT_ACTION,
        "signed-submit refusal",
    )
    require_path(
        payload,
        ["audit_event", "resource_id"],
        SIGNED_SUBMIT_RESOURCE_ID,
        "signed-submit refusal",
    )
    require_path(
        payload,
        ["audit_event", "metadata", "refusal_code"],
        disabled["code"],
        "signed-submit refusal",
    )
    require_path(
        payload,
        ["audit_event", "metadata", "resource_id_policy"],
        SIGNED_SUBMIT_RESOURCE_ID,
        "signed-submit refusal",
    )
    require_list_contains(
        payload,
        "request_fields",
        disabled["request_fields"],
        "signed-submit refusal",
    )
    require_list_contains(
        payload,
        "refusal_guards",
        [
            "default mode refuses mutation",
            "test-only signed-submit verifier is not enabled",
            "pending state is not changed",
            "chain state is not changed",
        ],
        "signed-submit refusal",
    )
    forbidden = find_forbidden_markers(payload)
    if forbidden:
        raise SmokeError(f"signed-submit refusal leaked forbidden markers: {forbidden}")


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)

    envelope = load_json(ENVELOPE_FIXTURE)
    disabled = load_json(DISABLED_FIXTURE)
    validate_disabled_fixture(disabled)
    write_json(artifact_dir / "signed-submit-disabled-fixture.json", disabled)
    write_json(artifact_dir / "test-only-signed-transfer-envelope.json", envelope)

    completed: list[str] = ["validated signed-submit disabled fixture"]
    if not args.skip_build:
        if "CARGO_TARGET_DIR" not in os.environ:
            os.environ["CARGO_TARGET_DIR"] = str(artifact_dir / "cargo-target")
            completed.append("using isolated cargo target directory")
        run_command(
            "build XRIQ signed-submit refusal smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("built xriq-node and xriq-api")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "phase1-4-signed-submit-refusal-chain.bin"
    preflight_pending_file = artifact_dir / "phase1-4-signed-submit-refusal-preflight.tsv"
    pending_file = artifact_dir / "phase1-4-signed-submit-refusal-pending.tsv"

    base_transfer = run_json(
        "create Phase 1.4 signed-submit refusal base chain",
        [
            str(node_binary),
            "preflight-transfer",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(preflight_pending_file),
            "--alice-balance",
            "100",
            "--from",
            ALICE,
            "--to",
            BOB,
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    base_tx_hash = require_hash(
        base_transfer.get("transaction_hash") or base_transfer.get("tx_hash"),
        "Phase 1.4 signed-submit refusal base transaction hash",
    )
    write_json(artifact_dir / "base-confirmed-transfer.json", base_transfer)
    completed.append("created base confirmed transfer")

    local_request_id = "phase1-4-signed-submit-disabled-smoke"
    target = build_signed_submit_target(envelope, local_request_id)
    disabled_response = assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        target,
        403,
        artifact_dir / "signed-submit-disabled-response.json",
        lambda payload: validate_signed_submit_refusal(payload, disabled),
    )
    if pending_file.exists():
        raise SmokeError("signed-submit disabled route created or changed the pending file")
    completed.append("verified signed-submit default refusal without pending mutation")

    summary = {
        "ok": "xriq-phase1-4-signed-submit-refusal-smoke",
        "completed_at": datetime.now(UTC).isoformat(),
        "endpoint": SIGNED_SUBMIT_ENDPOINT,
        "local_request_id": local_request_id,
        "base_transaction_hash": base_tx_hash,
        "refusal_code": disabled_response["code"],
        "audit_event_id": disabled_response["audit_event"]["event_id"],
        "pending_file_created": pending_file.exists(),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "artifacts": {
            "fixture": str(artifact_dir / "signed-submit-disabled-fixture.json"),
            "envelope": str(artifact_dir / "test-only-signed-transfer-envelope.json"),
            "base_transfer": str(artifact_dir / "base-confirmed-transfer.json"),
            "disabled_response": str(artifact_dir / "signed-submit-disabled-response.json"),
        },
        "completed": completed,
        "scope_boundaries": [
            "local/private signed-submit refusal smoke only",
            "no accepted signed-submit mutation",
            "no wallet submit UI mutation",
            "no browser key generation or storage",
            "no custody or hosted signing",
            "no public network, DEX, bridge, smart-contract, asset issuance, production infrastructure, or tag action",
        ],
    }
    summary["artifact_dir"] = str(artifact_dir)
    write_json(artifact_dir / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_smoke(args)
    except SmokeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

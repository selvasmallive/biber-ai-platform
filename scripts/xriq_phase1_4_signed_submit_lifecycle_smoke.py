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
    CAROL,
    FEES,
    SmokeError,
    assert_api_method_status,
    assert_api_status,
    executable_path,
    repo_root,
    require_equal,
    require_hash,
    require_list,
    run_command,
    run_json,
    write_json,
)


PRODUCER = "xriqdev1author00000000000"
SIGNED_SUBMIT_ENDPOINT = "POST /api/v1/wallet/transfers/submit-signed"
SIGNED_SUBMIT_FLAG = "--enable-local-wallet-submit-signed"
BLOCK_PRODUCTION_FLAG = "--enable-local-block-production"
EXPECTED_SIGNED_FORMAT = "xriq-local-signed-transfer-envelope-v1"


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-4-signed-submit-lifecycle-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.4 local/private signed-submit lifecycle smoke: "
            "signed artifact -> accepted pending submit -> produced block -> read-back checks."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for lifecycle smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node, xriq-api, and xriq-wallet debug binaries.",
    )
    return parser.parse_args(argv)


def run_wallet_signed_artifact(wallet_binary: Path, xriq_dir: Path) -> dict[str, Any]:
    output = run_command(
        "create Phase 1.4 signed-transfer artifact",
        [
            str(wallet_binary),
            "signed-transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            ALICE,
            "--to",
            CAROL,
            "--amount",
            "5",
            "--fee",
            "2",
            "--nonce",
            "1",
            "--signer-label",
            "alice",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    try:
        artifact = json.loads(output)
    except json.JSONDecodeError as error:
        raise SmokeError(f"signed-transfer artifact was not valid JSON: {error}") from error
    if not isinstance(artifact, dict):
        raise SmokeError("signed-transfer artifact must be a JSON object")
    return artifact


def validate_signed_artifact(artifact: dict[str, Any]) -> dict[str, str]:
    context = "Phase 1.4 signed artifact"
    require_equal(artifact, "format_version", EXPECTED_SIGNED_FORMAT, context)
    require_equal(artifact, "warning", "local-private-devnet-test-signature-only", context)
    require_equal(artifact, "environment", "private-devnet", context)
    require_equal(artifact, "network", "xriq-devnet", context)

    scope = artifact.get("scope")
    if not isinstance(scope, dict):
        raise SmokeError(f"{context}: expected scope object")
    for key, expected in {
        "local_private_only": True,
        "test_identity_only": True,
        "non_mutating": True,
        "browser_key_material_allowed": False,
        "custody_allowed": False,
        "public_network_allowed": False,
        "dex_allowed": False,
        "production_infrastructure_allowed": False,
    }.items():
        require_equal(scope, key, expected, context)

    signer = artifact.get("signer")
    if not isinstance(signer, dict):
        raise SmokeError(f"{context}: expected signer object")
    require_equal(signer, "label", "alice", context)
    require_equal(signer, "address", ALICE, context)

    tx = artifact.get("transaction")
    if not isinstance(tx, dict):
        raise SmokeError(f"{context}: expected transaction object")
    require_equal(tx, "version", 1, context)
    require_equal(tx, "chain_id", "xriq-devnet", context)
    require_equal(tx, "from", ALICE, context)
    require_equal(tx, "to", CAROL, context)
    require_equal(tx, "amount_base_units", "5", context)
    require_equal(tx, "fee_base_units", "2", context)
    require_equal(tx, "nonce", 1, context)
    require_equal(tx, "expires_at_height", 100, context)

    hashes = artifact.get("hashes")
    if not isinstance(hashes, dict):
        raise SmokeError(f"{context}: expected hashes object")
    signing_hash = require_hash(hashes.get("transaction_signing_hash"), f"{context} signing hash")
    tx_hash = require_hash(hashes.get("transaction_hash"), f"{context} transaction hash")

    signature = artifact.get("signature_envelope")
    if not isinstance(signature, dict):
        raise SmokeError(f"{context}: expected signature_envelope object")
    require_equal(signature, "algorithm", "test-only", context)
    require_equal(signature, "signature_encoding", "test-only-prefix-plus-signing-hash", context)
    require_equal(signature, "verification", "TestOnlySignatureVerifier.verify_transaction", context)

    preview = artifact.get("submit_request_preview")
    if not isinstance(preview, dict):
        raise SmokeError(f"{context}: expected submit_request_preview object")
    require_equal(preview, "endpoint", SIGNED_SUBMIT_ENDPOINT, context)
    require_equal(preview, "required_enablement", SIGNED_SUBMIT_FLAG, context)
    require_equal(preview, "mutation_when_disabled", "none", context)
    require_equal(preview, "mutation_when_accepted", "pending_state_only", context)
    return {"transaction_signing_hash": signing_hash, "transaction_hash": tx_hash}


def signed_submit_target(artifact: dict[str, Any], local_request_id: str) -> str:
    tx = artifact["transaction"]
    hashes = artifact["hashes"]
    signature = artifact["signature_envelope"]
    params = [
        ("local_request_id", local_request_id),
        ("format_version", artifact["format_version"]),
        ("version", tx["version"]),
        ("chain_id", tx["chain_id"]),
        ("from_address", tx["from"]),
        ("to_address", tx["to"]),
        ("amount_base_units", tx["amount_base_units"]),
        ("fee_base_units", tx["fee_base_units"]),
        ("nonce", tx["nonce"]),
        ("expires_at_height", tx["expires_at_height"]),
        ("transaction_signing_hash", hashes["transaction_signing_hash"]),
        ("transaction_hash", hashes["transaction_hash"]),
        ("signature_algorithm", signature["algorithm"]),
        ("signature_encoding", signature["signature_encoding"]),
    ]
    return "/api/v1/wallet/transfers/submit-signed?" + urlencode(params)


def ensure_no_sensitive_markers(payload: Any, context: str) -> None:
    forbidden = {
        "private_key",
        "seed_phrase",
        "mnemonic",
        "secret_key",
        "raw_signature",
        "custody_account",
        "public_network_endpoint",
        "dex_route",
    }
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in forbidden:
                found.append(key)
            ensure_no_sensitive_markers(value, context)
    elif isinstance(payload, list):
        for item in payload:
            ensure_no_sensitive_markers(item, context)
    if found:
        raise SmokeError(f"{context}: forbidden sensitive fields leaked: {sorted(set(found))}")


def validate_signed_submit_accepted(
    payload: dict[str, Any],
    *,
    artifact: dict[str, Any],
    chain_file: Path,
    pending_file: Path,
    local_request_id: str,
) -> str:
    context = "Phase 1.4 signed-submit accepted"
    tx = artifact["transaction"]
    hashes = artifact["hashes"]
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", SIGNED_SUBMIT_ENDPOINT, context)
    require_equal(payload, "code", "signed_submit_accepted_local_only", context)
    require_equal(payload, "status", "pending", context)
    require_equal(payload, "mutation", "pending_state_only", context)
    require_equal(payload, "warning", "local-private-devnet-test-signature-only", context)

    transaction = payload.get("transaction")
    if not isinstance(transaction, dict):
        raise SmokeError(f"{context}: expected transaction object")
    tx_hash = require_hash(transaction.get("tx_hash"), f"{context} tx hash")
    require_equal(transaction, "tx_hash", hashes["transaction_hash"], context)
    require_equal(transaction, "status", "pending", context)
    require_equal(transaction, "from_address", tx["from"], context)
    require_equal(transaction, "to_address", tx["to"], context)
    require_equal(transaction, "amount_base_units", tx["amount_base_units"], context)
    require_equal(transaction, "fee_base_units", tx["fee_base_units"], context)
    require_equal(transaction, "nonce", tx["nonce"], context)
    require_equal(transaction, "expires_at_height", tx["expires_at_height"], context)
    require_equal(transaction, "block_height", None, context)
    require_equal(transaction, "transaction_index", None, context)

    verification = payload.get("verification")
    if not isinstance(verification, dict):
        raise SmokeError(f"{context}: expected verification object")
    require_equal(verification, "signature_algorithm", "test-only", context)
    require_equal(verification, "transaction_signing_hash", hashes["transaction_signing_hash"], context)
    require_equal(verification, "transaction_hash", hashes["transaction_hash"], context)
    require_equal(verification, "verifier", "TestOnlySignatureVerifier", context)
    require_equal(verification, "verified", True, context)

    pending_state = payload.get("pending_state")
    if not isinstance(pending_state, dict):
        raise SmokeError(f"{context}: expected pending_state object")
    require_equal(pending_state, "before_count", 0, context)
    require_equal(pending_state, "after_count", 1, context)
    require_equal(pending_state, "added_tx_hash", tx_hash, context)
    require_equal(pending_state, "pending_file", str(pending_file), context)

    chain_state = payload.get("chain_state")
    if not isinstance(chain_state, dict):
        raise SmokeError(f"{context}: expected chain_state object")
    require_equal(chain_state, "current_height", 1, context)
    require_hash(chain_state.get("latest_block_hash"), f"{context} latest block")
    require_equal(chain_state, "chain_file", str(chain_file), context)
    require_equal(chain_state, "chain_unchanged", True, context)

    require_equal(payload, "audit_event_recorded", True, context)
    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise SmokeError(f"{context}: expected audit_event object")
    require_equal(audit_event, "event_id", f"signed-submit-accepted:{local_request_id}", context)
    require_equal(audit_event, "actor", "local-private-devnet-operator", context)
    require_equal(audit_event, "action", "wallet_transfer_signed_submit_attempt", context)
    require_equal(audit_event, "resource_type", "wallet_transfer", context)
    require_equal(audit_event, "resource_id", tx_hash, context)
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise SmokeError(f"{context}: expected audit metadata object")
    require_equal(metadata, "outcome", "accepted", context)
    require_equal(metadata, "status", "pending", context)
    require_equal(metadata, "explicit_flag", SIGNED_SUBMIT_FLAG, context)
    require_equal(metadata, "local_request_id", local_request_id, context)
    require_equal(metadata, "added_tx_hash", tx_hash, context)
    policy = metadata.get("metadata_policy")
    if not isinstance(policy, str) or "no key material or custody material" not in policy:
        raise SmokeError(f"{context}: metadata policy must forbid key and custody material")
    ensure_no_sensitive_markers(payload, context)
    return tx_hash


def validate_pending_status(payload: dict[str, Any], *, tx_hash: str) -> None:
    context = "Phase 1.4 pending wallet status"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "tx_hash", tx_hash, context)
    require_equal(payload, "status", "pending", context)


def validate_block_production(
    payload: dict[str, Any],
    *,
    tx_hash: str,
    chain_file: Path,
    pending_file: Path,
    local_request_id: str,
) -> str:
    context = "Phase 1.4 signed-submit block production"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", "POST /api/v1/blocks/produce", context)
    require_equal(payload, "code", "block_production_accepted_local_only", context)
    require_equal(payload, "status", "confirmed", context)
    require_equal(payload, "mutation", "chain_and_pending_state_local_only", context)
    require_equal(payload, "warning", "local-private-devnet-only", context)

    block = payload.get("block")
    if not isinstance(block, dict):
        raise SmokeError(f"{context}: expected block object")
    require_equal(block, "height", 2, context)
    block_hash = require_hash(block.get("block_hash"), f"{context} block hash")
    require_equal(block, "transaction_count", 1, context)
    require_equal(block, "timestamp_utc", "1970-01-01T00:00:02Z", context)

    confirmed_transactions = require_list(payload.get("confirmed_transactions"), context)
    if len(confirmed_transactions) != 1 or not isinstance(confirmed_transactions[0], dict):
        raise SmokeError(f"{context}: expected exactly one confirmed transaction")
    confirmed = confirmed_transactions[0]
    require_equal(confirmed, "tx_hash", tx_hash, context)
    require_equal(confirmed, "status", "confirmed", context)
    require_equal(confirmed, "block_height", 2, context)
    require_equal(confirmed, "block_hash", block_hash, context)
    require_equal(confirmed, "transaction_index", 0, context)

    pending_state = payload.get("pending_state")
    if not isinstance(pending_state, dict):
        raise SmokeError(f"{context}: expected pending_state object")
    require_equal(pending_state, "before_count", 1, context)
    require_equal(pending_state, "after_count", 0, context)
    require_equal(pending_state, "removed_tx_hashes", [tx_hash], context)
    require_equal(pending_state, "pending_file", str(pending_file), context)

    chain_state = payload.get("chain_state")
    if not isinstance(chain_state, dict):
        raise SmokeError(f"{context}: expected chain_state object")
    require_equal(chain_state, "previous_height", 1, context)
    require_equal(chain_state, "current_height", 2, context)
    require_equal(chain_state, "chain_file", str(chain_file), context)

    require_equal(payload, "audit_scope", "api-local-accepted", context)
    require_equal(payload, "audit_event_recorded", True, context)
    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise SmokeError(f"{context}: expected audit_event object")
    require_equal(audit_event, "event_id", f"block-production:{local_request_id}", context)
    require_equal(audit_event, "action", "block_production_attempt", context)
    require_equal(audit_event, "resource_type", "block_production", context)
    require_equal(audit_event, "resource_id", local_request_id, context)
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise SmokeError(f"{context}: expected audit metadata object")
    require_equal(metadata, "explicit_flag", BLOCK_PRODUCTION_FLAG, context)
    require_equal(metadata, "local_request_id", local_request_id, context)
    require_equal(metadata, "producer", PRODUCER, context)
    require_equal(metadata, "confirmed_transaction_count", 1, context)
    ensure_no_sensitive_markers(payload, context)
    return block_hash


def validate_confirmed_status(payload: dict[str, Any], *, tx_hash: str) -> None:
    context = "Phase 1.4 confirmed wallet status"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "tx_hash", tx_hash, context)
    require_equal(payload, "status", "confirmed", context)
    require_equal(payload, "block_height", 2, context)
    require_hash(payload.get("block_hash"), f"{context} block hash")
    require_equal(payload, "transaction_index", 0, context)


def validate_mempool_empty(payload: dict[str, Any]) -> None:
    context = "Phase 1.4 mempool"
    require_equal(payload, "pending_count", 0, context)
    entries = require_list(payload.get("entries"), context)
    if entries:
        raise SmokeError(f"{context}: expected empty mempool after block production")


def validate_network(payload: dict[str, Any]) -> None:
    context = "Phase 1.4 network"
    require_equal(payload, "current_height", 2, context)
    require_hash(payload.get("latest_block_hash"), f"{context} latest block")
    require_hash(payload.get("state_root"), f"{context} state root")


def validate_explorer(payload: dict[str, Any]) -> None:
    context = "Phase 1.4 explorer overview"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    chain = payload.get("chain")
    totals = payload.get("totals")
    if not isinstance(chain, dict) or not isinstance(totals, dict):
        raise SmokeError(f"{context}: expected chain and totals objects")
    require_equal(chain, "current_height", 2, context)
    require_equal(chain, "stored_blocks", 2, context)
    require_equal(chain, "pending_transactions", 0, context)
    require_equal(totals, "transactions", 2, context)


def validate_account(payload: dict[str, Any], *, address: str, balance: str, nonce: int) -> None:
    context = f"Phase 1.4 account {address}"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "address", address, context)
    require_equal(payload, "balance_base_units", balance, context)
    require_equal(payload, "nonce", nonce, context)


def validate_history(
    payload: dict[str, Any],
    *,
    address: str,
    tx_hash: str,
    expected_direction: str,
    min_rows: int,
) -> None:
    context = f"Phase 1.4 history {address}"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "address", address, context)
    transactions = require_list(payload.get("transactions"), context)
    if len(transactions) < min_rows:
        raise SmokeError(f"{context}: expected at least {min_rows} history rows")
    matching = [
        transaction
        for transaction in transactions
        if isinstance(transaction, dict)
        and transaction.get("tx_hash") == tx_hash
        and transaction.get("direction") == expected_direction
    ]
    if not matching:
        raise SmokeError(f"{context}: missing {expected_direction} row for {tx_hash}")


def validate_admin_audit(payload: dict[str, Any]) -> None:
    context = "Phase 1.4 admin audit"
    require_equal(payload, "environment", "private-devnet", context)
    local_events = require_list(payload.get("local_refusal_audit_events"), context)
    available_actions = {
        str(event.get("action")) for event in local_events if isinstance(event, dict)
    }
    for action in {
        "wallet_transfer_submit_attempt",
        "wallet_transfer_send_attempt",
        "wallet_transfer_signed_submit_attempt",
        "block_production_attempt",
    }:
        if action not in available_actions:
            raise SmokeError(f"{context}: missing local audit catalog action {action}")


def validate_disabled_signed_submit(payload: dict[str, Any]) -> None:
    context = "Phase 1.4 disabled signed-submit"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "code", "signed_submit_disabled", context)
    require_equal(payload, "mutation", "none", context)
    require_equal(payload, "enabled", False, context)


def validate_invalid_signed_submit(payload: dict[str, Any]) -> None:
    context = "Phase 1.4 invalid signed-submit"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "code", "unsupported_signature_algorithm", context)
    require_equal(payload, "mutation", "none", context)
    verification = payload.get("verification")
    if not isinstance(verification, dict):
        raise SmokeError(f"{context}: expected verification object")
    require_equal(verification, "pending_write_allowed", False, context)


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    api_dir = artifact_dir / "api"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    completed: list[str] = []

    if not args.skip_build:
        if "CARGO_TARGET_DIR" not in os.environ:
            os.environ["CARGO_TARGET_DIR"] = str(artifact_dir / "cargo-target")
            completed.append("using isolated cargo target directory")
        run_command(
            "build XRIQ Phase 1.4 signed-submit lifecycle binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api", "-p", "xriq-wallet"],
            cwd=xriq_dir,
        )
        completed.append("built xriq-node, xriq-api, and xriq-wallet")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    wallet_binary = executable_path(xriq_dir, "xriq-wallet")
    for binary in [node_binary, api_binary, wallet_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "phase1-4-signed-submit-lifecycle-chain.bin"
    pending_file = artifact_dir / "phase1-4-signed-submit-lifecycle-pending.tsv"
    preflight_pending_file = artifact_dir / "phase1-4-signed-submit-lifecycle-preflight.tsv"

    base_transfer = run_json(
        "create Phase 1.4 signed-submit lifecycle base chain",
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
        "Phase 1.4 base transaction hash",
    )
    require_equal(base_transfer, "confirmed_block_height", 1, "Phase 1.4 base transfer")
    require_equal(base_transfer, "final_balance_base_units", "73", "Phase 1.4 base transfer")
    require_equal(base_transfer, "final_nonce", 1, "Phase 1.4 base transfer")
    write_json(artifact_dir / "base-confirmed-transfer.json", base_transfer)
    pending_file.write_text("", encoding="utf-8")
    completed.append("created base confirmed transfer")

    signed_artifact = run_wallet_signed_artifact(wallet_binary, xriq_dir)
    hashes = validate_signed_artifact(signed_artifact)
    write_json(artifact_dir / "signed-transfer-artifact.json", signed_artifact)
    completed.append("created and validated signed-transfer artifact")

    signed_local_request_id = "phase1-4-signed-submit-lifecycle-1"
    target = signed_submit_target(signed_artifact, signed_local_request_id)
    disabled_pending_before = pending_file.read_text(encoding="utf-8")
    assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        target,
        403,
        api_dir / "signed-submit-disabled-default.json",
        validate_disabled_signed_submit,
    )
    if pending_file.read_text(encoding="utf-8") != disabled_pending_before:
        raise SmokeError("default disabled signed-submit mutated the pending file")
    completed.append("verified signed-submit default refusal")

    invalid_target = target.replace("signature_algorithm=test-only", "signature_algorithm=not-test-only")
    assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        invalid_target,
        400,
        api_dir / "signed-submit-invalid-signature.json",
        validate_invalid_signed_submit,
        extra_args=[SIGNED_SUBMIT_FLAG, "true"],
    )
    if pending_file.read_text(encoding="utf-8") != disabled_pending_before:
        raise SmokeError("invalid signed-submit mutated the pending file")
    completed.append("verified invalid signed-submit refusal")

    signed_submit = assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        target,
        201,
        api_dir / "signed-submit-accepted-local.json",
        lambda payload: None,
        extra_args=[SIGNED_SUBMIT_FLAG, "true"],
    )
    tx_hash = validate_signed_submit_accepted(
        signed_submit,
        artifact=signed_artifact,
        chain_file=chain_file,
        pending_file=pending_file,
        local_request_id=signed_local_request_id,
    )
    write_json(api_dir / "signed-submit-accepted-local.json", signed_submit)
    if tx_hash != hashes["transaction_hash"]:
        raise SmokeError("accepted signed-submit hash did not match signed artifact hash")
    if tx_hash not in pending_file.read_text(encoding="utf-8"):
        raise SmokeError("accepted signed-submit did not append the pending transaction")
    completed.append("accepted signed-submit to pending")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        f"/api/v1/wallet/transactions/{tx_hash}/status",
        200,
        api_dir / "signed-submit-pending-status.json",
        lambda payload: validate_pending_status(payload, tx_hash=tx_hash),
    )
    completed.append("verified signed-submit pending status")

    block_local_request_id = "phase1-4-signed-submit-lifecycle-2"
    block_target = (
        f"/api/v1/blocks/produce?local_request_id={block_local_request_id}"
        f"&producer={PRODUCER}&max_transactions=4&timestamp_ms=2000"
    )
    produced_block = assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        block_target,
        201,
        api_dir / "signed-submit-produced-block-local.json",
        lambda payload: None,
        extra_args=[BLOCK_PRODUCTION_FLAG, "true"],
    )
    block_hash = validate_block_production(
        produced_block,
        tx_hash=tx_hash,
        chain_file=chain_file,
        pending_file=pending_file,
        local_request_id=block_local_request_id,
    )
    write_json(api_dir / "signed-submit-produced-block-local.json", produced_block)
    if pending_file.read_text(encoding="utf-8") != "":
        raise SmokeError("block production did not clear the signed-submit pending file")
    completed.append("produced signed-submit transaction into one local block")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        f"/api/v1/wallet/transactions/{tx_hash}/status",
        200,
        api_dir / "signed-submit-confirmed-status.json",
        lambda payload: validate_confirmed_status(payload, tx_hash=tx_hash),
    )
    completed.append("verified signed-submit confirmed status")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "/api/v1/mempool?limit=5",
        200,
        api_dir / "mempool-empty-after-signed-submit.json",
        validate_mempool_empty,
    )
    completed.append("verified mempool empty after block production")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "/api/v1/network",
        200,
        api_dir / "network-after-signed-submit.json",
        validate_network,
    )
    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "/api/v1/explorer/overview",
        200,
        api_dir / "explorer-overview-after-signed-submit.json",
        validate_explorer,
    )
    completed.append("verified network and explorer after signed-submit block")

    accounts = {
        ALICE: ("66", 2),
        BOB: ("25", 0),
        CAROL: ("5", 0),
        FEES: ("4", 0),
    }
    for address, (balance, nonce) in accounts.items():
        assert_api_status(
            api_binary,
            xriq_dir,
            chain_file,
            pending_file,
            f"/api/v1/wallet/accounts/{address}/balance",
            200,
            api_dir / f"wallet-balance-{address}.json",
            lambda payload, address=address, balance=balance, nonce=nonce: validate_account(
                payload,
                address=address,
                balance=balance,
                nonce=nonce,
            ),
        )
    completed.append("verified wallet balances after signed-submit block")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        f"/api/v1/wallet/accounts/{ALICE}/history?limit=5",
        200,
        api_dir / "wallet-history-sender.json",
        lambda payload: validate_history(
            payload,
            address=ALICE,
            tx_hash=tx_hash,
            expected_direction="sent",
            min_rows=2,
        ),
    )
    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        f"/api/v1/wallet/accounts/{CAROL}/history?limit=5",
        200,
        api_dir / "wallet-history-recipient.json",
        lambda payload: validate_history(
            payload,
            address=CAROL,
            tx_hash=tx_hash,
            expected_direction="received",
            min_rows=1,
        ),
    )
    completed.append("verified wallet histories after signed-submit block")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "/api/v1/admin/audit-events?limit=10",
        200,
        api_dir / "admin-audit-events.json",
        validate_admin_audit,
    )
    completed.append("verified admin audit catalog visibility")

    summary = {
        "ok": "xriq-phase1-4-signed-submit-lifecycle-smoke",
        "completed_at": datetime.now(UTC).isoformat(),
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "signed_submit_tx_hash": tx_hash,
        "signed_submit_signing_hash": hashes["transaction_signing_hash"],
        "produced_block_hash": block_hash,
        "artifacts": {
            "base_confirmed_transfer": str(artifact_dir / "base-confirmed-transfer.json"),
            "signed_transfer_artifact": str(artifact_dir / "signed-transfer-artifact.json"),
            "signed_submit_disabled_default": str(api_dir / "signed-submit-disabled-default.json"),
            "signed_submit_invalid_signature": str(api_dir / "signed-submit-invalid-signature.json"),
            "signed_submit_accepted": str(api_dir / "signed-submit-accepted-local.json"),
            "signed_submit_pending_status": str(api_dir / "signed-submit-pending-status.json"),
            "signed_submit_produced_block": str(api_dir / "signed-submit-produced-block-local.json"),
            "signed_submit_confirmed_status": str(api_dir / "signed-submit-confirmed-status.json"),
            "mempool_empty": str(api_dir / "mempool-empty-after-signed-submit.json"),
            "network": str(api_dir / "network-after-signed-submit.json"),
            "explorer": str(api_dir / "explorer-overview-after-signed-submit.json"),
            "admin_audit": str(api_dir / "admin-audit-events.json"),
        },
        "guards": [
            "CPU-only request-mode smoke",
            "signed artifact is CLI-only and test-identity-only",
            "signed-submit default path remains refused and non-mutating",
            "invalid signed-submit remains refused and non-mutating",
            "accepted signed-submit requires --enable-local-wallet-submit-signed true",
            "accepted signed-submit appends exactly one pending transaction",
            "block production requires --enable-local-block-production true",
            "block production confirms the same signed-submit transaction",
            "pending file is empty after confirmation",
            "no UI mutation control is enabled",
            "no browser key material, custody material, public network, DEX, production infrastructure, or tag action",
        ],
        "completed": completed,
    }
    write_json(artifact_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        run_smoke(parse_args(argv))
    except SmokeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

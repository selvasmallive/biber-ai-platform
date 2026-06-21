#!/usr/bin/env python3
"""XRIQ Phase 2 restart/recovery smoke.

Local/private only. This smoke proves that the private-devnet pending and chain
files survive process restarts and that a corrupted pending file recovers
instead of bricking startup. Each xriq-node/xriq-api invocation is a fresh
process, so it exercises true restart semantics: state is reconstructed from the
chain and pending files every time.

It covers the Phase 2 hardening items:
- accepted signed-submit persists to the pending file,
- a clean restart replays the pending transaction,
- a duplicate pending line replays idempotently (no double count, no brick),
- a corrupt pending line is quarantined to a sidecar and self-healed out of the
  live pending file (no silent loss),
- block production confirms the transaction and clears pending across restart.

This smoke creates no tags, touches no secrets or cloud resources, enables no UI
mutation, and does not change the default-refused signed-submit contract.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xriq_phase1_1_local_e2e_smoke import (
    ALICE,
    BOB,
    CAROL,
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
from xriq_phase1_4_signed_submit_lifecycle_smoke import (
    BLOCK_PRODUCTION_FLAG,
    PRODUCER,
    SIGNED_SUBMIT_FLAG,
    run_wallet_signed_artifact,
    signed_submit_target,
    validate_signed_artifact,
)


QUARANTINE_MARKER = "xriq-pending-quarantine-v1"
CORRUPT_PENDING_LINE = "xriq-pending-transaction-v1\tnot-a-valid-record"


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase2-restart-recovery-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 2 restart/recovery smoke: accepted signed-submit "
            "persists, survives restarts, and recovers from duplicate/corrupt "
            "pending lines without bricking startup."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for restart/recovery smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node, xriq-api, and xriq-wallet debug binaries.",
    )
    return parser.parse_args(argv)


def pending_lines(pending_file: Path) -> list[str]:
    text = pending_file.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if line.strip()]


def append_pending_line(pending_file: Path, line: str) -> None:
    with pending_file.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def node_mempool_pending_count(
    node_binary: Path,
    xriq_dir: Path,
    chain_file: Path,
    pending_file: Path,
    *,
    label: str,
) -> dict[str, Any]:
    payload = run_json(
        f"xriq-node mempool-detail ({label})",
        [
            str(node_binary),
            "mempool-detail",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(pending_file),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    require_equal(payload, "command", "mempool-detail", f"restart mempool-detail ({label})")
    return payload


def require_pending_count(payload: dict[str, Any], expected: int, context: str) -> None:
    require_equal(payload, "pending_count", expected, context)


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
            "build XRIQ Phase 2 restart/recovery binaries",
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

    chain_file = artifact_dir / "phase2-restart-recovery-chain.bin"
    pending_file = artifact_dir / "phase2-restart-recovery-pending.tsv"
    preflight_pending_file = artifact_dir / "phase2-restart-recovery-preflight.tsv"
    quarantine_file = Path(str(pending_file) + ".quarantine")

    # 1. Base confirmed transfer establishes chain height 1 and bumps the alice
    #    nonce to 1, then the live pending file starts empty.
    base_transfer = run_json(
        "create Phase 2 restart/recovery base chain",
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
    require_equal(base_transfer, "confirmed_block_height", 1, "Phase 2 base transfer")
    pending_file.write_text("", encoding="utf-8")
    completed.append("created base confirmed transfer")

    # 2. Accepted signed-submit appends one pending transaction.
    signed_artifact = run_wallet_signed_artifact(wallet_binary, xriq_dir)
    hashes = validate_signed_artifact(signed_artifact)
    tx_hash = hashes["transaction_hash"]
    write_json(artifact_dir / "signed-transfer-artifact.json", signed_artifact)

    local_request_id = "phase2-restart-recovery-1"
    target = signed_submit_target(signed_artifact, local_request_id)
    accepted = assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        target,
        201,
        api_dir / "signed-submit-accepted.json",
        lambda payload: require_equal(
            payload, "code", "signed_submit_accepted_local_only", "Phase 2 accepted signed-submit"
        ),
        extra_args=[SIGNED_SUBMIT_FLAG, "true"],
    )
    require_equal(accepted, "status", "pending", "Phase 2 accepted signed-submit")
    if len(pending_lines(pending_file)) != 1:
        raise SmokeError("accepted signed-submit must append exactly one pending line")
    completed.append("accepted signed-submit to pending")

    # 3. Clean restart: the pending transaction replays from the file.
    restart1 = node_mempool_pending_count(
        node_binary, xriq_dir, chain_file, pending_file, label="clean-restart"
    )
    require_pending_count(restart1, 1, "Phase 2 clean restart")
    if tx_hash not in json.dumps(restart1):
        raise SmokeError("clean restart did not replay the accepted transaction")
    completed.append("verified pending transaction survives a clean restart")

    # 4. Duplicate pending line (e.g. crash mid-append) replays idempotently.
    existing_lines = pending_lines(pending_file)
    append_pending_line(pending_file, existing_lines[0])
    if len(pending_lines(pending_file)) != 2:
        raise SmokeError("duplicate injection did not produce two pending lines")
    restart2 = node_mempool_pending_count(
        node_binary, xriq_dir, chain_file, pending_file, label="duplicate-recovery"
    )
    require_pending_count(restart2, 1, "Phase 2 duplicate recovery")
    completed.append("verified duplicate pending line replays idempotently")

    # 5. Corrupt pending line is quarantined and self-healed out of the file.
    append_pending_line(pending_file, CORRUPT_PENDING_LINE)
    restart3 = node_mempool_pending_count(
        node_binary, xriq_dir, chain_file, pending_file, label="corrupt-recovery"
    )
    require_pending_count(restart3, 1, "Phase 2 corrupt recovery")
    healed = pending_file.read_text(encoding="utf-8")
    if "not-a-valid-record" in healed:
        raise SmokeError("corrupt pending line was not removed from the live pending file")
    if not quarantine_file.exists():
        raise SmokeError("corrupt pending line was not written to the quarantine sidecar")
    quarantined = quarantine_file.read_text(encoding="utf-8")
    if QUARANTINE_MARKER not in quarantined or "not-a-valid-record" not in quarantined:
        raise SmokeError("quarantine sidecar is missing the marker or corrupt content")
    completed.append("verified corrupt pending line is quarantined without silent loss")

    # 6. Block production confirms the transaction and clears pending; the
    #    confirmation survives a final restart.
    block_local_request_id = "phase2-restart-recovery-2"
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
        api_dir / "produced-block.json",
        lambda payload: require_equal(
            payload, "status", "confirmed", "Phase 2 block production"
        ),
        extra_args=[BLOCK_PRODUCTION_FLAG, "true"],
    )
    block = produced_block.get("block")
    if not isinstance(block, dict):
        raise SmokeError("Phase 2 block production: expected block object")
    block_hash = require_hash(block.get("block_hash"), "Phase 2 produced block hash")
    if pending_lines(pending_file):
        raise SmokeError("block production did not clear the pending file")

    restart4 = node_mempool_pending_count(
        node_binary, xriq_dir, chain_file, pending_file, label="post-block-restart"
    )
    require_pending_count(restart4, 0, "Phase 2 post-block restart")
    completed.append("verified block confirms transaction and clears pending across restart")

    summary = {
        "ok": "xriq-phase2-restart-recovery-smoke",
        "completed_at": datetime.now(UTC).isoformat(),
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "quarantine_file": str(quarantine_file),
        "signed_submit_tx_hash": tx_hash,
        "produced_block_hash": block_hash,
        "guards": [
            "CPU-only request-mode smoke",
            "each xriq-node/xriq-api invocation is a fresh process (restart semantics)",
            "accepted signed-submit requires --enable-local-wallet-submit-signed true",
            "pending transaction survives a clean restart",
            "duplicate pending line replays idempotently",
            "corrupt pending line is quarantined to a sidecar without silent loss",
            "block production requires --enable-local-block-production true",
            "block confirms the transaction and clears pending across restart",
            "no UI mutation, browser key material, custody, public network, DEX, "
            "production infrastructure, or tag action",
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

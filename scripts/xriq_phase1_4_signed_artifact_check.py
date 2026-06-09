#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
XRIQ_DIR = ROOT / "xriq"
TARGET_DIR = XRIQ_DIR / "target"

EXPECTED_FORMAT_VERSION = "xriq-local-signed-transfer-envelope-v1"
EXPECTED_WARNING = "local-private-devnet-test-signature-only"
EXPECTED_ENDPOINT = "POST /api/v1/wallet/transfers/submit-signed"
EXPECTED_ENABLEMENT = "--enable-local-wallet-submit-signed"


class SignedArtifactCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the XRIQ Phase 1.4 CLI-only local signed-transfer artifact."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for check output. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-4-signed-artifact-check-{timestamp}"


def run_wallet(args: list[str]) -> str:
    completed = subprocess.run(
        ["cargo", "run", "-q", "-p", "xriq-wallet", "--", *args],
        cwd=XRIQ_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SignedArtifactCheckError(
            f"xriq-wallet {' '.join(args)} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SignedArtifactCheckError(f"{label}: expected 64 lowercase hex hash, got {value!r}")
    return value


def require_equal(payload: dict[str, Any], key: str, expected: Any, label: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise SignedArtifactCheckError(f"{label}: expected {key}={expected!r}, got {actual!r}")


def require_nested(payload: dict[str, Any], path: list[str], expected: Any, label: str) -> None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise SignedArtifactCheckError(f"{label}: missing {'.'.join(path)}")
        value = value[key]
    if value != expected:
        raise SignedArtifactCheckError(
            f"{label}: expected {'.'.join(path)}={expected!r}, got {value!r}"
        )


def verify_json_artifact(text: str) -> dict[str, Any]:
    if "xriq-test-only-signature" in text:
        raise SignedArtifactCheckError("JSON artifact leaked raw test signature prefix")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise SignedArtifactCheckError(f"wallet JSON output is invalid: {error}") from error
    if not isinstance(payload, dict):
        raise SignedArtifactCheckError("wallet JSON output must be an object")

    require_equal(payload, "format_version", EXPECTED_FORMAT_VERSION, "json artifact")
    require_equal(payload, "warning", EXPECTED_WARNING, "json artifact")
    require_equal(payload, "environment", "private-devnet", "json artifact")
    require_equal(payload, "network", "xriq-devnet", "json artifact")
    require_nested(payload, ["scope", "local_private_only"], True, "json artifact")
    require_nested(payload, ["scope", "test_identity_only"], True, "json artifact")
    require_nested(payload, ["scope", "non_mutating"], True, "json artifact")
    require_nested(payload, ["scope", "browser_key_material_allowed"], False, "json artifact")
    require_nested(payload, ["scope", "custody_allowed"], False, "json artifact")
    require_nested(payload, ["scope", "public_network_allowed"], False, "json artifact")
    require_nested(payload, ["scope", "dex_allowed"], False, "json artifact")
    require_nested(payload, ["signer", "label"], "alice", "json artifact")
    require_nested(payload, ["signer", "address"], "xriqdev1alice00000000000", "json artifact")
    require_nested(payload, ["transaction", "from"], "xriqdev1alice00000000000", "json artifact")
    require_nested(payload, ["transaction", "to"], "xriqdev1carol00000000000", "json artifact")
    require_nested(payload, ["transaction", "amount_base_units"], "5", "json artifact")
    require_nested(payload, ["transaction", "fee_base_units"], "2", "json artifact")
    require_nested(payload, ["transaction", "nonce"], 1, "json artifact")
    signing_hash = require_hash(
        payload.get("hashes", {}).get("transaction_signing_hash"),
        "json artifact transaction_signing_hash",
    )
    tx_hash = require_hash(
        payload.get("hashes", {}).get("transaction_hash"),
        "json artifact transaction_hash",
    )
    require_nested(payload, ["signature_envelope", "algorithm"], "test-only", "json artifact")
    require_nested(payload, ["signature_envelope", "algorithm_id"], 0, "json artifact")
    require_nested(
        payload,
        ["signature_envelope", "verification"],
        "TestOnlySignatureVerifier.verify_transaction",
        "json artifact",
    )
    require_nested(payload, ["submit_request_preview", "endpoint"], EXPECTED_ENDPOINT, "json artifact")
    require_nested(
        payload,
        ["submit_request_preview", "required_enablement"],
        EXPECTED_ENABLEMENT,
        "json artifact",
    )
    require_nested(payload, ["submit_request_preview", "mutation_when_disabled"], "none", "json artifact")
    require_nested(
        payload,
        ["submit_request_preview", "mutation_when_accepted"],
        "pending_state_only",
        "json artifact",
    )
    forbidden_fields = payload.get("forbidden_fields")
    if not isinstance(forbidden_fields, list):
        raise SignedArtifactCheckError("json artifact missing forbidden_fields list")
    for marker in ["private_key", "seed_phrase", "mnemonic", "secret_key", "raw_signature"]:
        if marker not in forbidden_fields:
            raise SignedArtifactCheckError(f"json artifact forbidden_fields missing {marker}")
    return {"transaction_signing_hash": signing_hash, "transaction_hash": tx_hash}


def verify_text_artifact(text: str, hashes: dict[str, Any]) -> None:
    required = [
        f"warning={EXPECTED_WARNING}",
        f"format_version={EXPECTED_FORMAT_VERSION}",
        "environment=private-devnet",
        "network=xriq-devnet",
        "signer_label=alice",
        "signer_address=xriqdev1alice00000000000",
        f"transaction_signing_hash={hashes['transaction_signing_hash']}",
        f"transaction_hash={hashes['transaction_hash']}",
        "signature_algorithm=test-only",
        "signature_algorithm_id=0",
        "signature_bytes=60",
        "mutation_when_disabled=none",
        "mutation_when_accepted=pending_state_only",
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise SignedArtifactCheckError(f"text artifact missing markers: {missing}")
    forbidden = ["private_key", "seed", "mnemonic", "secret_key", "xriq-test-only-signature"]
    found = [marker for marker in forbidden if marker in text]
    if found:
        raise SignedArtifactCheckError(f"text artifact leaked forbidden markers: {found}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_args = [
        "signed-transfer",
        "--chain-id",
        "xriq-devnet",
        "--from",
        "xriqdev1alice00000000000",
        "--to",
        "xriqdev1carol00000000000",
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
    ]
    try:
        json_text = run_wallet([*base_args, "--format", "json"])
        hashes = verify_json_artifact(json_text)
        text_output = run_wallet(base_args)
        verify_text_artifact(text_output, hashes)
        summary = {
            "ok": "xriq-phase1-4-signed-artifact-check",
            "completed_at": datetime.now(UTC).isoformat(),
            "command": "cargo run -q -p xriq-wallet -- signed-transfer ...",
            "format_version": EXPECTED_FORMAT_VERSION,
            "warning": EXPECTED_WARNING,
            "transaction_signing_hash": hashes["transaction_signing_hash"],
            "transaction_hash": hashes["transaction_hash"],
            "scope_boundaries": [
                "CLI-only local/private test signed artifact",
                "accepted API signed-submit mutation is covered separately behind explicit local flag",
                "no wallet submit UI mutation",
                "no browser key generation or storage",
                "no custody or hosted signing",
                "no public network, DEX, bridge, smart-contract, asset issuance, production infrastructure, or tag action",
            ],
        }
        artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
        summary["artifact_dir"] = str(artifact_dir)
        write_json(artifact_dir / "summary.json", summary)
        write_json(artifact_dir / "signed-transfer.json", json.loads(json_text))
        (artifact_dir / "signed-transfer.txt").write_text(text_output + "\n", encoding="utf-8")
    except SignedArtifactCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

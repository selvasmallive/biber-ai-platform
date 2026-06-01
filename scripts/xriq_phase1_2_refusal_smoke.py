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
        "extra_guard": "audit event is required before any future accepted mutation",
    },
    "wallet-transfer-send-disabled.json": {
        "endpoint": "POST /api/v1/wallet/transfers/send",
        "code": "wallet_send_disabled",
        "explicit_flag": "--enable-local-wallet-send",
        "extra_guard": "pending state is not changed",
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
        summary = {
            "ok": "xriq-phase1-2-refusal-smoke",
            "artifact_dir": str(artifact_dir),
            "fixture_dir": str(FIXTURE_DIR),
            "fixtures_checked": len(checked),
            "fixtures": checked,
            "guards": [
                "disabled_by_default",
                "mutation_none",
                "explicit_local_private_flag_required",
                "audit_event_required",
                "test_identity_only",
                "no_signing_or_custody_fields",
            ],
            "next": (
                "add UI/client refusal coverage before any successful "
                "local mutation path"
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

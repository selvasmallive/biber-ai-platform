#!/usr/bin/env python3
"""XRIQ Phase 2 staging smokes runner.

Single entry point a clean clone can use to run the Phase 2 local/private smokes,
including the staging-devnet environment profile. It builds the xriq-node,
xriq-api, and xriq-wallet binaries once and then runs:

- the Phase 1.4 signed-submit lifecycle smoke (default local profile), and
- the Phase 2 restart/recovery smoke under the staging-devnet profile.

This is local/private only. It creates no cloud resources, handles no secrets,
creates no tags, and changes no runtime state beyond local temp artifacts.

Usage from a clean clone:

    python scripts/xriq_phase2_staging_smokes.py

On Windows/OneDrive, point CARGO_TARGET_DIR outside the OneDrive tree to avoid
transient linker locks, e.g.:

    CARGO_TARGET_DIR="$HOME/xriq-target" python scripts/xriq_phase2_staging_smokes.py
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
    SmokeError,
    repo_root,
    run_command,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the XRIQ Phase 2 staging smokes (lifecycle + restart/recovery)."
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node, xriq-api, and xriq-wallet debug binaries.",
    )
    return parser.parse_args(argv)


def run_smokes(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    completed: list[str] = []

    if not args.skip_build:
        run_command(
            "build XRIQ Phase 2 staging-smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api", "-p", "xriq-wallet"],
            cwd=xriq_dir,
        )
        completed.append("built xriq-node, xriq-api, and xriq-wallet")

    # The smokes reuse the binaries just built (or already present).
    run_command(
        "Phase 1.4 signed-submit lifecycle smoke (local)",
        [
            sys.executable,
            str(root / "scripts" / "xriq_phase1_4_signed_submit_lifecycle_smoke.py"),
            "--skip-build",
        ],
        cwd=root,
        capture=False,
    )
    completed.append("lifecycle smoke passed (local)")

    run_command(
        "Phase 2 restart/recovery smoke (staging-devnet)",
        [
            sys.executable,
            str(root / "scripts" / "xriq_phase2_restart_recovery_smoke.py"),
            "--skip-build",
            "--environment",
            "staging-devnet",
        ],
        cwd=root,
        capture=False,
    )
    completed.append("restart/recovery smoke passed (staging-devnet)")

    summary = {
        "ok": "xriq-phase2-staging-smokes",
        "completed_at": datetime.now(UTC).isoformat(),
        "cargo_target_dir": os.environ.get("CARGO_TARGET_DIR", "(default xriq/target)"),
        "smokes": [
            "xriq_phase1_4_signed_submit_lifecycle_smoke.py (local)",
            "xriq_phase2_restart_recovery_smoke.py --environment staging-devnet",
        ],
        "guards": [
            "clean clone can build and run the Phase 2 staging smokes",
            "staging-devnet environment profile is exercised end-to-end",
            "no cloud resources, secrets, tags, or public network behavior",
        ],
        "completed": completed,
    }
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        run_smokes(parse_args(argv))
    except SmokeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

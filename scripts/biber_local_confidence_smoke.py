#!/usr/bin/env python3
"""Run BIBER's no-GPU local confidence smokes as one pre-live-provider check."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_smoke_script(
    *,
    repo_root: Path,
    script_name: str,
    pycache_root: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(pycache_root / Path(script_name).stem)
    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / script_name)],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed with exit code {completed.returncode}: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{script_name} did not print a JSON object: {completed.stdout!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{script_name} did not print a JSON object.")
    return payload


def compact_check(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "source": payload.get("source"),
        "ok": payload.get("ok") is True,
        "api_required": payload.get("api_required") is True,
        "gpu_required": payload.get("gpu_required") is True,
        "mentor_used": payload.get("mentor_used") is True,
        "training_allowed": payload.get("training_allowed") is True,
    }


def run_confidence_smoke(timeout_seconds: float) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="biber-local-confidence-pycache-") as tmp:
        pycache_root = Path(tmp)
        provider = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_openai_provider_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        repair_loop = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_repair_loop_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )

    checks = [
        compact_check("local_openai_provider_http", provider),
        compact_check("local_repair_loop", repair_loop),
    ]
    summary = {
        "source": "biber_local_confidence_smoke",
        "ok": all(check["ok"] for check in checks),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "checks": checks,
        "provider": {
            "request_path": provider.get("request_path"),
            "request_model": provider.get("request_model"),
            "response_model": provider.get("response_model"),
            "content_edit_paths": provider.get("content_edit_paths"),
        },
        "repair_loop": {
            "chain_status": repair_loop.get("chain_status"),
            "verification_ok": repair_loop.get("verification_ok"),
            "status_next_action": repair_loop.get("status_next_action"),
            "model_response_source": repair_loop.get("model_response_source"),
        },
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run BIBER's local provider HTTP smoke and local repair-loop smoke "
            "as one no-GPU confidence gate."
        )
    )
    parser.add_argument("--output", help="Optional path for the confidence summary JSON.")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_confidence_smoke(args.timeout_seconds)
    if args.output:
        write_json(Path(args.output), summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

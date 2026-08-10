#!/usr/bin/env python3
"""Run BIBER live-provider confidence smokes as one GPU-friendly gate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8001/v1"
DEFAULT_MODEL = "biber-dev-core"


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def default_output_root() -> Path:
    env_root = os.getenv("BIBER_LIVE_CONFIDENCE_SMOKE_OUTPUT_ROOT")
    if env_root:
        return Path(env_root)
    workspace_outputs = Path("/workspace/outputs")
    if workspace_outputs.is_dir():
        return workspace_outputs
    return Path(tempfile.gettempdir())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_json_script(
    *,
    repo_root: Path,
    pycache_root: Path,
    timeout_seconds: float,
    script_name: str,
    args: list[str],
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(pycache_root / Path(script_name).stem)
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / script_name),
            *args,
        ],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=timeout_seconds,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{script_name} did not return JSON: exit={completed.returncode} "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{script_name} returned non-object JSON")
    if completed.returncode != 0 or payload.get("ok") is not True:
        raise RuntimeError(
            f"{script_name} failed: exit={completed.returncode} "
            f"payload={json.dumps(payload, indent=2, sort_keys=True)}"
        )
    return payload


def compact_check(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "source": payload.get("source"),
        "ok": payload.get("ok") is True,
        "gpu_required": payload.get("gpu_required") is True,
        "live_provider_required": payload.get("live_provider_required") is True,
        "api_required": payload.get("api_required") is True,
        "mentor_used": payload.get("mentor_used") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "github_request_sent": payload.get("github_request_sent") is True,
    }


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = Path(args.output_root) if args.output_root else default_output_root()
    work_root = output_root / f"biber-live-provider-confidence-{timestamp()}"
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    pycache_root = work_root / "pycache"

    if args.mode == "live":
        readiness = run_json_script(
            repo_root=repo_root,
            pycache_root=pycache_root,
            timeout_seconds=args.readiness_timeout_seconds,
            script_name="biber_live_provider_readiness.py",
            args=[
                "--base-url",
                args.base_url,
                "--model",
                args.model,
                "--require-ready",
                "--require-model",
            ],
        )
    else:
        readiness = run_json_script(
            repo_root=repo_root,
            pycache_root=pycache_root,
            timeout_seconds=args.command_timeout_seconds,
            script_name="biber_live_provider_readiness_smoke.py",
            args=[],
        )
    write_json(artifact_dir / "readiness.json", readiness)

    fixture_plan = run_json_script(
        repo_root=repo_root,
        pycache_root=pycache_root,
        timeout_seconds=args.command_timeout_seconds,
        script_name="biber_live_provider_fixture_plan_smoke.py",
        args=[
            "--mode",
            args.mode,
            "--base-url",
            args.base_url,
            "--model",
            args.model,
            "--output-root",
            str(work_root),
            "--output",
            str(artifact_dir / "fixture-plan.json"),
        ],
    )
    repair_args = [
        "--mode",
        args.mode,
        "--base-url",
        args.base_url,
        "--model",
        args.model,
        "--output-root",
        str(work_root),
        "--output",
        str(artifact_dir / "disposable-repair.json"),
    ]
    if args.skip_repair_apply:
        repair_args.append("--skip-apply")
    disposable_repair = run_json_script(
        repo_root=repo_root,
        pycache_root=pycache_root,
        timeout_seconds=args.command_timeout_seconds,
        script_name="biber_live_provider_repair_smoke.py",
        args=repair_args,
    )

    checks = [
        compact_check("live_provider_readiness", readiness),
        compact_check("live_fixture_plan", fixture_plan),
        compact_check("live_disposable_repair", disposable_repair),
    ]
    unsafe_flags = [
        check
        for check in checks
        if check["api_required"]
        or check["mentor_used"]
        or check["training_allowed"]
        or check["github_request_sent"]
    ]
    ok = (
        all(check["ok"] for check in checks)
        and not unsafe_flags
        and fixture_plan.get("mutation_performed") is False
        and disposable_repair.get("auto_saved") is False
        and disposable_repair.get("target_is_disposable") is True
    )
    summary = {
        "source": "biber_live_provider_confidence_smoke",
        "ok": ok,
        "mode": args.mode,
        "base_url": args.base_url,
        "model": args.model,
        "external_network_required": False,
        "gpu_required": args.mode == "live",
        "api_required": False,
        "live_provider_required": args.mode == "live",
        "mentor_used": False,
        "training_allowed": False,
        "github_request_sent": False,
        "auto_saved": False,
        "work_root": str(work_root),
        "artifact_dir": str(artifact_dir),
        "checks": checks,
        "unsafe_flags": unsafe_flags,
        "readiness": {
            "ok": readiness.get("ok"),
            "model_available": readiness.get("model_available"),
            "available_model_count": readiness.get("available_model_count"),
        },
        "fixture_plan": {
            "ok": fixture_plan.get("ok"),
            "chain_status": fixture_plan.get("chain_status"),
            "review_status": fixture_plan.get("review_status"),
            "planned": fixture_plan.get("planned"),
            "rejected": fixture_plan.get("rejected"),
            "plan_hash": fixture_plan.get("plan_hash"),
            "mutation_performed": fixture_plan.get("mutation_performed"),
            "artifact_dir": fixture_plan.get("real_repo_plan_artifact_dir"),
        },
        "disposable_repair": {
            "ok": disposable_repair.get("ok"),
            "chain_status": disposable_repair.get("chain_status"),
            "review_status": disposable_repair.get("review_status"),
            "apply_status": disposable_repair.get("apply_status"),
            "verification_status": disposable_repair.get("verification_status"),
            "test_ok": disposable_repair.get("test_ok"),
            "plan_hash": disposable_repair.get("plan_hash"),
            "target_is_disposable": disposable_repair.get("target_is_disposable"),
            "artifact_dir": disposable_repair.get("artifact_dir"),
        },
    }
    if args.output:
        write_json(Path(args.output), summary)
    if args.cleanup and ok:
        shutil.rmtree(work_root)
        summary["work_root_cleanup"] = "deleted_after_success"
    if not ok:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run BIBER's live-provider readiness, fixture plan-only, and "
            "disposable repair smokes as one GPU-friendly confidence gate."
        )
    )
    parser.add_argument("--mode", choices=["live", "mock"], default="live")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument(
        "--model",
        default=(
            os.getenv("BIBER_LOCAL_OPENAI_MODEL")
            or os.getenv("BIBER_LOCAL_MODEL_NAME")
            or DEFAULT_MODEL
        ),
    )
    parser.add_argument("--output-root")
    parser.add_argument("--output")
    parser.add_argument("--readiness-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--command-timeout-seconds", type=float, default=240.0)
    parser.add_argument("--skip-repair-apply", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run_smoke(args)
    except Exception as exc:
        print(f"biber_live_provider_confidence_smoke: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run a disposable BIBER live-provider repair smoke.

The default mode uses the local OpenAI-compatible provider wrapper against a
live endpoint such as vLLM on Vast. The target repo is always created by this
script under a smoke work directory, so the guarded apply step can safely use
the normal explicit-approval client command without touching a real repo.
"""

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

import biber_live_provider_readiness as live_readiness


DEFAULT_BASE_URL = "http://127.0.0.1:8001/v1"
DEFAULT_MODEL = "biber-dev-core"
DEFAULT_TIMEOUT_SECONDS = 180.0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_output_root() -> Path:
    env_root = os.getenv("BIBER_LIVE_REPAIR_SMOKE_OUTPUT_ROOT")
    if env_root:
        return Path(env_root)
    workspace_outputs = Path("/workspace/outputs")
    if workspace_outputs.is_dir():
        return workspace_outputs
    return Path(tempfile.gettempdir())


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def run_client(
    repo_root: Path,
    artifact_dir: Path,
    *args: str,
    env_updates: dict[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(artifact_dir / "pycache")
    if env_updates:
        env.update(env_updates)
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "biber_agent_client.py"),
        "--json",
        *args,
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"biber_agent_client.py failed with exit code {completed.returncode}: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError("biber_agent_client.py did not return a JSON object")
    return parsed


def create_target_repo(target_root: Path) -> None:
    (target_root / "app").mkdir(parents=True)
    (target_root / "src").mkdir(parents=True)
    (target_root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (target_root / "src" / "app.py").write_text(
        "def answer(:\n    return 1\n",
        encoding="utf-8",
    )
    (target_root / "README.md").write_text(
        "# Live provider repair fixture\n",
        encoding="utf-8",
    )


def create_mock_provider(path: Path) -> None:
    path.write_text(
        "import json\n"
        "import sys\n"
        "\n"
        "request = json.load(sys.stdin)\n"
        "repair = request.get('repair_request') or {}\n"
        "prompt = repair.get('repair_prompt') or ''\n"
        "if request.get('source') != 'biber_local_model_command_request':\n"
        "    raise SystemExit('unexpected request source')\n"
        "if 'BIBER_FILE_CONTENT_START' not in prompt or 'def answer(:' not in prompt:\n"
        "    raise SystemExit('exact source context missing from prompt')\n"
        "content = '''```json\\n{\\n  \"edits\": [\\n    {\\n"
        "      \"path\": \"src/app.py\",\\n"
        "      \"old_text\": \"def answer(:\\\\n    return 1\\\\n\",\\n"
        "      \"new_text\": \"def answer():\\\\n    return 1\\\\n\",\\n"
        "      \"expected_replacements\": 1\\n    }\\n  ]\\n}\\n```'''\n"
        "print(json.dumps({'content': content, 'model': request.get('model')}))\n",
        encoding="utf-8",
    )


def default_model_command(repo_root: Path) -> str:
    return json.dumps(
        [
            sys.executable,
            str(repo_root / "scripts" / "biber_local_openai_provider.py"),
        ]
    )


def ensure_disposable_target(work_root: Path, target_root: Path) -> None:
    resolved_work = work_root.resolve()
    resolved_target = target_root.resolve()
    if resolved_target == resolved_work or resolved_work not in resolved_target.parents:
        raise RuntimeError(f"Refusing to apply outside smoke work root: {resolved_target}")


def build_summary(
    *,
    args: argparse.Namespace,
    base_url: str,
    model: str,
    work_root: Path,
    artifact_dir: Path,
    target_root: Path,
    readiness: dict[str, Any] | None,
    mvp_result: dict[str, Any],
    repair_request: dict[str, Any],
    chain: dict[str, Any],
    review: dict[str, Any],
    apply_result: dict[str, Any] | None,
    verification: dict[str, Any] | None,
    status: dict[str, Any] | None,
) -> dict[str, Any]:
    plan = chain.get("repair_edit_plan")
    if not isinstance(plan, dict):
        plan = {}
    final_source = (target_root / "src" / "app.py").read_text(encoding="utf-8")
    fixed_signature_ok = args.skip_apply or "def answer():" in final_source
    apply_ok = args.skip_apply or (
        isinstance(apply_result, dict)
        and apply_result.get("apply_status") == "applied"
        and isinstance(verification, dict)
        and verification.get("chain_status") == "verified"
        and verification.get("test_ok") is True
    )
    readiness_ok = True if readiness is None else readiness.get("ok") is True
    ok = (
        readiness_ok
        and mvp_result.get("ok") is False
        and mvp_result.get("test_ok") is False
        and repair_request.get("source_context_snippets_available") is True
        and chain.get("chain_status") == "planned"
        and review.get("review_status") == "ready_for_explicit_apply_approval"
        and review.get("apply_recommendation") == "ready_for_explicit_apply_approval"
        and review.get("blockers") == []
        and plan.get("plan_hash") == review.get("plan_hash")
        and apply_ok
        and fixed_signature_ok
    )
    summary = {
        "source": "biber_live_provider_repair_smoke",
        "ok": ok,
        "mode": args.mode,
        "base_url": base_url,
        "model": model,
        "external_network_required": (
            bool(readiness.get("external_network_required")) if readiness else False
        ),
        "gpu_required": args.mode == "live",
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "live_provider_required": args.mode == "live",
        "auto_saved": False,
        "target_is_disposable": True,
        "work_root": str(work_root),
        "artifact_dir": str(artifact_dir),
        "target_root": str(target_root),
        "readiness_ok": readiness_ok,
        "mvp_test_ok": mvp_result.get("test_ok"),
        "source_context_snippets_available": repair_request.get(
            "source_context_snippets_available"
        ),
        "chain_status": chain.get("chain_status"),
        "review_status": review.get("review_status"),
        "apply_recommendation": review.get("apply_recommendation"),
        "blockers": review.get("blockers"),
        "planned": review.get("planned"),
        "rejected": review.get("rejected"),
        "plan_hash": review.get("plan_hash"),
        "apply_status": apply_result.get("apply_status") if apply_result else None,
        "verification_status": (
            verification.get("verification_status") if verification else None
        ),
        "verification_chain_status": (
            verification.get("chain_status") if verification else None
        ),
        "test_ok": verification.get("test_ok") if verification else None,
        "status_next_action": (
            (status.get("next_step") or {}).get("action")
            if isinstance(status, dict)
            else None
        ),
        "final_file_contains_fixed_signature": "def answer():" in final_source,
        "artifacts": {
            "failed_mvp_loop": str(artifact_dir / "failed-mvp-loop.json"),
            "prepared_repair": str(artifact_dir / "prepared-repair.json"),
            "local_repair_chain": str(artifact_dir / "local-repair-chain.json"),
            "local_repair_chain_review": str(
                artifact_dir / "local-repair-chain-review.json"
            ),
            "repair_edit_plan": str(artifact_dir / "repair-edit-plan.json"),
            "repair_edit_apply": str(artifact_dir / "repair-edit-apply.json"),
            "local_verify_chain": str(artifact_dir / "local-verify-chain.json"),
            "local_repair_loop_status": str(
                artifact_dir / "local-repair-loop-status.json"
            ),
        },
    }
    if readiness is not None:
        summary["readiness"] = readiness
    return summary


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    base_url = args.base_url or os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL)
    model = (
        args.model
        or os.getenv("BIBER_LOCAL_OPENAI_MODEL")
        or os.getenv("BIBER_LOCAL_MODEL_NAME")
        or DEFAULT_MODEL
    )
    output_root = Path(args.output_root) if args.output_root else default_output_root()
    work_root = output_root / f"biber-live-provider-repair-smoke-{timestamp()}"
    artifact_dir = work_root / "artifacts"
    target_root = work_root / "target-repo"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    create_target_repo(target_root)

    readiness: dict[str, Any] | None = None
    model_command = args.model_command
    if args.mode == "mock":
        mock_provider = work_root / "mock-local-model-provider.py"
        create_mock_provider(mock_provider)
        model_command = json.dumps([sys.executable, str(mock_provider)])
    else:
        readiness = live_readiness.readiness_summary(
            base_url=base_url,
            model=model,
            api_key_env=args.api_key_env,
            timeout_seconds=args.readiness_timeout_seconds,
            require_model=True,
        )
        write_json(artifact_dir / "live-provider-readiness.json", readiness)
        if args.require_ready and readiness.get("ok") is not True:
            summary = {
                "source": "biber_live_provider_repair_smoke",
                "ok": False,
                "mode": args.mode,
                "base_url": base_url,
                "model": model,
                "work_root": str(work_root),
                "artifact_dir": str(artifact_dir),
                "target_root": str(target_root),
                "readiness": readiness,
                "readiness_ok": False,
                "live_provider_required": True,
                "gpu_required": True,
                "api_required": False,
                "mentor_used": False,
                "training_allowed": False,
            }
            return summary

    if not model_command:
        model_command = default_model_command(repo_root)
    env_updates = {
        "BIBER_LOCAL_OPENAI_BASE_URL": base_url,
        "BIBER_LOCAL_OPENAI_MODEL": model,
    }
    mvp_result = run_client(
        repo_root,
        artifact_dir,
        "mvp-loop",
        "--instruction",
        "Fix the Python syntax error in the local fixture repo.",
        "--local-target-root",
        str(target_root),
        "--changed-path",
        "src/app.py",
        "--test-id",
        "python-compileall-api",
        "--output",
        str(artifact_dir / "failed-mvp-loop.json"),
        env_updates=env_updates,
        timeout_seconds=args.command_timeout_seconds,
    )
    repair_request = run_client(
        repo_root,
        artifact_dir,
        "prepare-repair",
        str(artifact_dir / "failed-mvp-loop.json"),
        "--output",
        str(artifact_dir / "prepared-repair.json"),
        env_updates=env_updates,
        timeout_seconds=args.command_timeout_seconds,
    )
    chain = run_client(
        repo_root,
        artifact_dir,
        "local-repair-chain",
        str(artifact_dir / "prepared-repair.json"),
        "--model-command",
        model_command,
        "--model-command-timeout-seconds",
        str(int(args.model_command_timeout_seconds)),
        "--target-root",
        str(target_root),
        "--output",
        str(artifact_dir / "local-repair-chain.json"),
        env_updates=env_updates,
        timeout_seconds=args.command_timeout_seconds + args.model_command_timeout_seconds,
    )
    review = run_client(
        repo_root,
        artifact_dir,
        "review-local-repair-chain",
        str(artifact_dir / "local-repair-chain.json"),
        "--output",
        str(artifact_dir / "local-repair-chain-review.json"),
        env_updates=env_updates,
        timeout_seconds=args.command_timeout_seconds,
    )
    plan = chain.get("repair_edit_plan")
    if not isinstance(plan, dict):
        raise RuntimeError("local-repair-chain did not include repair_edit_plan")
    write_json(artifact_dir / "repair-edit-plan.json", plan)

    apply_result: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    status: dict[str, Any] | None = None
    if not args.skip_apply:
        ensure_disposable_target(work_root, target_root)
        if review.get("review_status") != "ready_for_explicit_apply_approval":
            raise RuntimeError(f"Review is not ready for apply: {review}")
        apply_result = run_client(
            repo_root,
            artifact_dir,
            "apply-repair-edits",
            str(artifact_dir / "repair-edit-plan.json"),
            "--approve",
            "--review-artifact",
            str(artifact_dir / "local-repair-chain-review.json"),
            "--target-root",
            str(target_root),
            "--output",
            str(artifact_dir / "repair-edit-apply.json"),
            env_updates=env_updates,
            timeout_seconds=args.command_timeout_seconds,
        )
        verification = run_client(
            repo_root,
            artifact_dir,
            "local-verify-chain",
            str(artifact_dir / "repair-edit-apply.json"),
            "--target-root",
            str(target_root),
            "--diagnose-on-failure",
            "--output",
            str(artifact_dir / "local-verify-chain.json"),
            env_updates=env_updates,
            timeout_seconds=args.command_timeout_seconds,
        )
        status = run_client(
            repo_root,
            artifact_dir,
            "local-repair-loop-status",
            str(artifact_dir),
            "--output",
            str(artifact_dir / "local-repair-loop-status.json"),
            env_updates=env_updates,
            timeout_seconds=args.command_timeout_seconds,
        )

    summary = build_summary(
        args=args,
        base_url=base_url,
        model=model,
        work_root=work_root,
        artifact_dir=artifact_dir,
        target_root=target_root,
        readiness=readiness,
        mvp_result=mvp_result,
        repair_request=repair_request,
        chain=chain,
        review=review,
        apply_result=apply_result,
        verification=verification,
        status=status,
    )
    write_json(artifact_dir / "live-provider-repair-smoke-summary.json", summary)
    if args.cleanup and summary.get("ok") is True:
        shutil.rmtree(work_root, ignore_errors=True)
        summary["cleaned_up"] = True
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a disposable BIBER local repair flow against a live "
            "OpenAI-compatible provider. Use --mode mock for no-GPU validation."
        )
    )
    parser.add_argument("--mode", choices=["live", "mock"], default="live")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--model")
    parser.add_argument(
        "--api-key-env",
        default="BIBER_LOCAL_OPENAI_API_KEY",
        help="Environment variable containing an optional provider bearer token.",
    )
    parser.add_argument("--output-root")
    parser.add_argument(
        "--model-command",
        help=(
            "Optional JSON array command for local-repair-chain. Defaults to "
            "scripts/biber_local_openai_provider.py in live mode."
        ),
    )
    parser.add_argument("--model-command-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--command-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--readiness-timeout-seconds", type=float, default=10.0)
    parser.add_argument(
        "--require-ready",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="In live mode, stop when GET /v1/models readiness is not ok.",
    )
    parser.add_argument(
        "--skip-apply",
        action="store_true",
        help="Stop after review instead of applying to the disposable target repo.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the smoke work directory after a successful run.",
    )
    parser.add_argument("--output", help="Optional path for a copy of the summary JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run_smoke(args)
    except Exception as exc:
        print(f"biber_live_provider_repair_smoke: {exc}", file=sys.stderr)
        return 1
    if args.output:
        write_json(Path(args.output), summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run a no-API BIBER local MVP-loop full repair smoke test.

This smoke creates a temporary target repository with a Python syntax error,
runs scripts/biber_agent_client.py mvp-loop against it, then walks the failed
artifact through prepare-repair, a local model-command fixture, chain review,
guarded apply, local verification, and loop status. It is CPU-only and does not
resolve BIBER/OpenAI credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_client(repo_root: Path, artifact_dir: Path, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(artifact_dir / "pycache")
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
    (target_root / "src" / "app.py").write_bytes(b"def answer(:\n    return 1\n")
    (target_root / "README.md").write_text(
        "# Full repair fixture repo\n",
        encoding="utf-8",
    )


def create_fixture_model_provider(path: Path) -> None:
    path.write_text(
        "import json\n"
        "import sys\n"
        "\n"
        "request = json.load(sys.stdin)\n"
        "if request.get('source') != 'biber_local_model_command_request':\n"
        "    raise SystemExit('unexpected request source')\n"
        "repair = request.get('repair_request') or {}\n"
        "prompt = repair.get('repair_prompt') or ''\n"
        "if 'repair_hint: status=ready_for_prepare_repair' not in prompt:\n"
        "    raise SystemExit('repair hint missing from prompt')\n"
        "content = {\n"
        "    'edits': [\n"
        "        {\n"
        "            'path': 'src/app.py',\n"
        "            'old_text': 'def answer(:\\n    return 1\\n',\n"
        "            'new_text': 'def answer():\\n    return 2\\n',\n"
        "            'expected_replacements': 1,\n"
        "        }\n"
        "    ]\n"
        "}\n"
        "print(json.dumps({'model': request.get('model'), 'content': json.dumps(content)}))\n",
        encoding="utf-8",
    )


def run_smoke(work_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = work_root / "artifacts"
    target_root = work_root / "target-repo"
    artifact_dir.mkdir(parents=True)
    create_target_repo(target_root)

    mvp_artifact = artifact_dir / "failed-mvp-loop.json"
    prepared = artifact_dir / "prepared-repair.json"
    model_provider = work_root / "fixture-local-model-provider.py"
    local_chain = artifact_dir / "local-repair-chain.json"
    local_review = artifact_dir / "local-repair-chain-review.json"
    repair_plan = artifact_dir / "repair-edit-plan.json"
    repair_apply = artifact_dir / "repair-edit-apply.json"
    local_verify = artifact_dir / "local-verify-chain.json"
    loop_status = artifact_dir / "local-repair-loop-status.json"

    create_fixture_model_provider(model_provider)
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
        str(mvp_artifact),
    )
    agent_report = mvp_result.get("agent_report")
    if not isinstance(agent_report, dict):
        raise RuntimeError("failed mvp-loop did not include agent_report")
    repair_hint = agent_report.get("repair_hint")
    if not isinstance(repair_hint, dict):
        raise RuntimeError("failed mvp-loop did not include repair_hint")

    repair_request = run_client(
        repo_root,
        artifact_dir,
        "prepare-repair",
        str(mvp_artifact),
        "--output",
        str(prepared),
    )
    repair_prompt = str(repair_request.get("repair_prompt") or "")
    chain = run_client(
        repo_root,
        artifact_dir,
        "local-repair-chain",
        str(prepared),
        "--model-command",
        json.dumps([sys.executable, str(model_provider)]),
        "--model-command-timeout-seconds",
        "30",
        "--target-root",
        str(target_root),
        "--output",
        str(local_chain),
    )
    review = run_client(
        repo_root,
        artifact_dir,
        "review-local-repair-chain",
        str(local_chain),
        "--output",
        str(local_review),
    )
    plan = chain.get("repair_edit_plan")
    if not isinstance(plan, dict):
        raise RuntimeError("local-repair-chain did not produce repair_edit_plan")
    write_json(repair_plan, plan)
    apply_result = run_client(
        repo_root,
        artifact_dir,
        "apply-repair-edits",
        str(repair_plan),
        "--approve",
        "--review-artifact",
        str(local_review),
        "--output",
        str(repair_apply),
    )
    verification = run_client(
        repo_root,
        artifact_dir,
        "local-verify-chain",
        str(repair_apply),
        "--diagnose-on-failure",
        "--output",
        str(local_verify),
    )
    status = run_client(
        repo_root,
        artifact_dir,
        "local-repair-loop-status",
        str(artifact_dir),
        "--output",
        str(loop_status),
    )

    final_source = (target_root / "src" / "app.py").read_text(encoding="utf-8")
    summary = {
        "source": "biber_local_mvp_loop_full_repair_smoke",
        "ok": (
            mvp_result.get("ok") is False
            and mvp_result.get("test_ok") is False
            and repair_hint.get("status") == "ready_for_prepare_repair"
            and "repair_hint: status=ready_for_prepare_repair" in repair_prompt
            and chain.get("chain_status") == "planned"
            and (chain.get("model_response_source") or {}).get("source")
            == "local_model_command"
            and review.get("review_status") == "ready_for_explicit_apply_approval"
            and review.get("apply_recommendation")
            == "ready_for_explicit_apply_approval"
            and apply_result.get("apply_status") == "applied"
            and verification.get("chain_status") == "verified"
            and (status.get("next_step") or {}).get("action")
            == "human_review_verified_fix"
            and "def answer():" in final_source
            and "return 2" in final_source
        ),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "artifact_dir": str(artifact_dir),
        "target_root": str(target_root),
        "agent_report_status": agent_report.get("status"),
        "repair_hint_status": repair_hint.get("status"),
        "repair_prompt_has_hint": (
            "repair_hint: status=ready_for_prepare_repair" in repair_prompt
        ),
        "chain_status": chain.get("chain_status"),
        "review_status": review.get("review_status"),
        "apply_status": apply_result.get("apply_status"),
        "verification_status": verification.get("chain_status"),
        "status_next_action": (status.get("next_step") or {}).get("action"),
        "model_response_source": (chain.get("model_response_source") or {}).get(
            "source"
        ),
        "final_file_contains_return_2": "return 2" in final_source,
        "artifacts": {
            "mvp_artifact": str(mvp_artifact),
            "prepared": str(prepared),
            "model_provider": str(model_provider),
            "local_chain": str(local_chain),
            "local_review": str(local_review),
            "repair_plan": str(repair_plan),
            "repair_apply": str(repair_apply),
            "local_verify": str(local_verify),
            "loop_status": str(loop_status),
        },
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a no-API BIBER local MVP-loop full repair smoke test."
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary target repo and artifacts after the smoke run.",
    )
    parser.add_argument("--output", help="Optional path for the smoke summary JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_root = Path(tempfile.mkdtemp(prefix="biber-local-mvp-full-repair-smoke-"))
    try:
        summary = run_smoke(work_root)
        if args.keep_temp:
            summary["kept_temp"] = True
            summary["work_root"] = str(work_root)
        if args.output:
            write_json(Path(args.output), summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    finally:
        if not args.keep_temp:
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

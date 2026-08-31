#!/usr/bin/env python3
"""Offline smoke for the disposable BIBER Azure DevOps demo fixture."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "azure_devops_demo_fixture"
PATCH = FIXTURE / "patches" / "demo-pr-reviewable-change.diff"
README = FIXTURE / "README.md"
SOURCE = FIXTURE / "src" / "refund_policy.py"
TEST = FIXTURE / "tests" / "test_refund_policy.py"


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def run(command: list[str], *, cwd: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


def check_patch_in_temp_repo() -> dict[str, Any] | None:
    if not SOURCE.is_file() or not PATCH.is_file():
        return None
    with tempfile.TemporaryDirectory(prefix="biber-azdo-fixture-") as tmp_name:
        tmp = Path(tmp_name)
        relative_source = Path("examples/azure_devops_demo_fixture/src/refund_policy.py")
        target_source = tmp / relative_source
        target_source.parent.mkdir(parents=True, exist_ok=True)
        target_source.write_bytes(read_text(SOURCE).replace("\r\n", "\n").encode("utf-8"))
        target_patch = tmp / "demo-pr-reviewable-change.diff"
        target_patch.write_bytes(read_text(PATCH).replace("\r\n", "\n").encode("utf-8"))
        commands = [
            ["git", "init", "--quiet"],
            ["git", "config", "core.autocrlf", "false"],
            ["git", "config", "core.eol", "lf"],
            ["git", "config", "user.email", "biber-demo@example.invalid"],
            ["git", "config", "user.name", "BIBER Demo Fixture"],
            ["git", "add", str(relative_source).replace("\\", "/")],
            ["git", "commit", "--quiet", "-m", "Add base fixture"],
            ["git", "apply", "--check", "--unidiff-zero", str(target_patch)],
        ]
        attempts = []
        for command in commands:
            result = run(command, cwd=tmp)
            attempts.append(result)
            if not result["ok"]:
                return {
                    "command": command,
                    "exit_code": result["exit_code"],
                    "ok": False,
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "attempts": attempts,
                }
        return {"command": commands[-1], "exit_code": 0, "ok": True, "stdout": "", "stderr": "", "attempts": attempts}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args()

    readme = read_text(README)
    source = read_text(SOURCE)
    patch = read_text(PATCH)
    test = read_text(TEST)
    base_test = run([sys.executable, str(TEST)], cwd=ROOT) if TEST.is_file() else None
    patch_check = check_patch_in_temp_repo()

    checks = [
        check(README.is_file(), "fixture_readme_exists"),
        check(SOURCE.is_file(), "fixture_source_exists"),
        check(TEST.is_file(), "fixture_test_exists"),
        check(PATCH.is_file(), "fixture_patch_exists"),
        check("commentMode=dry-run" in readme, "readme_keeps_dry_run"),
        check("BIBER_API_KEY" in readme, "readme_mentions_secret_variable"),
        check("Do not replace it with a real secret" in readme, "readme_warns_fake_secret_only"),
        check("FAKE_DEMO_TOKEN_DO_NOT_USE" in patch, "patch_contains_fake_token_marker"),
        check("LOGGER.info" in patch, "patch_adds_reviewable_logging_risk"),
        check("amount_cents < 0" in patch, "patch_weakens_zero_amount_validation"),
        check("amount_cents <= 0" in source, "base_source_rejects_zero_amount"),
        check("unittest.main" in test, "test_is_stdlib_unittest"),
        check(bool(base_test and base_test["ok"]), "base_fixture_tests_pass", json.dumps(base_test or {})),
        check(bool(patch_check and patch_check["ok"]), "fixture_patch_applies_cleanly", json.dumps(patch_check or {})),
        check("OPENAI_API_KEY" not in readme + source + patch + test, "fixture_no_openai_key"),
        check("BIBER_ADMIN_API_KEY" not in readme + source + patch + test, "fixture_no_admin_key"),
        check("BIBER_TRAIN_APPROVED" not in readme + source + patch + test, "fixture_no_training_gate"),
    ]
    failed = [item for item in checks if not item["ok"]]
    result = {
        "source": "biber_azure_devops_demo_fixture_smoke",
        "ok": not failed,
        "status": "passed" if not failed else "failed",
        "api_required": False,
        "azure_devops_request_sent": False,
        "external_network_required": False,
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "fixture_root": str(FIXTURE),
        "patch": str(PATCH),
        "base_test": base_test,
        "patch_check": patch_check,
        "checks": checks,
        "failed": failed,
    }
    body = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")
    print(body, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

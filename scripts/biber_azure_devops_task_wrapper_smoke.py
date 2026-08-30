#!/usr/bin/env python3
"""Offline smoke for the packaged Azure DevOps task wrapper entrypoint."""

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


ROOT = Path(__file__).resolve().parents[1]
TASK_WRAPPER = (
    ROOT
    / "examples"
    / "azure_devops_extension"
    / "tasks"
    / "biber-ai-pr-review"
    / "v1"
    / "biber-ai-pr-review.js"
)


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(command: list[str], *, env: dict[str, str], timeout_seconds: float) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "command": command,
            "cwd": str(ROOT),
            "executed": True,
            "timed_out": False,
            "exit_code": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "cwd": str(ROOT),
            "executed": True,
            "timed_out": True,
            "exit_code": None,
            "ok": False,
            "stdout": (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "",
        }


def parse_stdout_json(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        parsed = json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument(
        "--allow-missing-node",
        action="store_true",
        help="Write a blocked artifact and exit 0 when node is unavailable.",
    )
    args = parser.parse_args()

    node = shutil.which("node")
    checks: list[dict[str, Any]] = [
        check(TASK_WRAPPER.is_file(), "task_wrapper_exists"),
        check(bool(node), "node_available"),
    ]
    blockers: list[str] = []
    command: dict[str, Any] | None = None
    payload: dict[str, Any] = {}
    markdown = ""
    artifact_dir = ""

    if not node:
        blockers.append("node_not_available")
    else:
        with tempfile.TemporaryDirectory(prefix="biber-azure-task-wrapper-") as tmp_name:
            tmp = Path(tmp_name)
            artifact_root = tmp / "artifacts"
            mock_diff = tmp / "mock.diff"
            mock_response = tmp / "mock-biber-response.json"
            mock_diff.write_text(
                """diff --git a/src/orders.ts b/src/orders.ts
--- a/src/orders.ts
+++ b/src/orders.ts
@@ -1,3 +1,6 @@
 export function canRefund(days: number): boolean {
+  const api_key = "secret-value-for-wrapper-redaction";
+  if (days < 0) return true;
   return days <= 30;
 }
""",
                encoding="utf-8",
            )
            mock_response.write_text(
                json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": (
                                        "### Summary\nRefund validation changed.\n\n"
                                        "### Risk level\nHigh risk.\n\n"
                                        "### Correctness risks\nNegative day counts should not pass.\n\n"
                                        "### Security/privacy risks\nSecret-like values must remain redacted.\n\n"
                                        "### Tests to run or add\nAdd negative and boundary tests.\n\n"
                                        "### Reviewer checklist\nConfirm no secret is committed.\n\n"
                                        "### Merge recommendation\nDo not merge until fixed."
                                    ),
                                }
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "BUILD_SOURCESDIRECTORY": str(ROOT),
                    "BUILD_ARTIFACTSTAGINGDIRECTORY": str(artifact_root),
                    "BIBER_API_KEY": "not-used-with-mock-response",
                    "BIBER_AZURE_DEVOPS_MOCK_DIFF_FILE": str(mock_diff),
                    "BIBER_AZURE_DEVOPS_MOCK_RESPONSE_FILE": str(mock_response),
                    "INPUT_BIBERAPIBASEURL": "https://api.beaverapi.com/v1",
                    "INPUT_BIBERMODEL": "biber-dev-core-v1",
                    "INPUT_COMMENTMODE": "dry-run",
                    "INPUT_MAXDIFFBYTES": "60000",
                }
            )
            command = run_command(
                [node, str(TASK_WRAPPER)],
                env=env,
                timeout_seconds=args.timeout_seconds,
            )
            output_json = artifact_root / "biber-ai-review.json"
            output_md = artifact_root / "biber-ai-review.md"
            payload = (
                json.loads(output_json.read_text(encoding="utf-8"))
                if output_json.is_file()
                else parse_stdout_json(command.get("stdout", ""))
            )
            markdown = output_md.read_text(encoding="utf-8") if output_md.is_file() else ""
            artifact_dir = str(artifact_root)

    if command is not None:
        checks.extend(
            [
                check(command.get("ok") is True, "wrapper_command_ok"),
                check(payload.get("ok") is True, "review_payload_ok"),
                check(payload.get("biber_request_sent") is False, "mock_no_biber_request"),
                check(payload.get("azure_comment_request_sent") is False, "dry_run_no_comment"),
                check(payload.get("mentor_used") is False, "mentor_unused"),
                check(payload.get("training_allowed") is False, "training_disallowed"),
                check(payload.get("risk_level") == "high", "risk_high_from_review"),
                check(
                    payload.get("secret_like_values_redacted", 0) >= 1,
                    "secret_redaction_count",
                ),
                check("secret-value-for-wrapper-redaction" not in markdown, "markdown_secret_redacted"),
                check("BIBER AI Review" in markdown, "markdown_header"),
            ]
        )

    failed_commands = [] if command is None or command.get("ok") else [command]
    ok = all(item["ok"] for item in checks) and not blockers and not failed_commands
    status = "passed" if ok else ("blocked" if blockers and not failed_commands else "failed")
    result = {
        "source": "biber_azure_devops_task_wrapper_smoke",
        "ok": ok,
        "status": status,
        "api_required": False,
        "external_network_required": False,
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "task_wrapper": str(TASK_WRAPPER),
        "artifact_dir": artifact_dir,
        "node": node,
        "checks": checks,
        "command": command,
        "blockers": blockers,
        "failed": [item for item in checks if not item["ok"]]
        + [
            {
                "name": "command:" + " ".join(command["command"]),
                "ok": False,
                "detail": command.get("stderr") or command.get("stdout") or "",
            }
            for command in failed_commands
        ],
    }
    if args.output:
        write_json(Path(args.output), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if ok or (args.allow_missing_node and blockers == ["node_not_available"]):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

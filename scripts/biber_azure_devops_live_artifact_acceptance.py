#!/usr/bin/env python3
"""Acceptance checks for the first BIBER Azure DevOps dry-run artifact.

Default validation is local-only: it reads a downloaded/published artifact
folder and checks that the first PR review output stayed dry-run, redacted, and
human-review-only. Use --self-test to generate the same artifact shape with a
mock response and the checked-in disposable fixture; that mode sends no BIBER,
Azure DevOps, GitHub, OpenAI, GPU, or training request.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "biber-dev-core-v1"
DEFAULT_ARTIFACT_DIR_ENV = "BIBER_AZURE_DEVOPS_ARTIFACT_DIR"
EXPECTED_SOURCE = "biber_azure_devops_pr_review"
EXPECTED_FIXTURE_PATH = "examples/azure_devops_demo_fixture/src/refund_policy.py"
FIXTURE_PATCH = ROOT / "examples" / "azure_devops_demo_fixture" / "patches" / "demo-pr-reviewable-change.diff"
PR_REVIEW_SCRIPT = ROOT / "scripts" / "biber_azure_devops_pr_review.py"

SECRET_LEAK_PATTERNS = [
    (
        "raw_key_assignment",
        re.compile(
            r"(?i)\b(?:BIBER_API_KEY|BIBER_ADMIN_API_KEY|OPENAI_API_KEY|AZURE_DEVOPS_EXT_PAT|SYSTEM_ACCESSTOKEN)\s*[:=]\s*(?!\[REDACTED_BIBER_SECRET\])\S+"
        ),
    ),
    (
        "raw_authorization_bearer",
        re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+(?!\[REDACTED_BIBER_SECRET\])\S+"),
    ),
    (
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    ),
    ("raw_demo_secret_marker", re.compile(r"FAKE_DEMO_TOKEN_DO_NOT_USE")),
]


class ArtifactError(RuntimeError):
    pass


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def read_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None


def discover_artifact_file(artifact_dir: Path, filename: str) -> Path | None:
    direct = artifact_dir / filename
    if direct.is_file():
        return direct
    matches = sorted(path for path in artifact_dir.rglob(filename) if path.is_file())
    return matches[0] if matches else None


def resolve_artifact_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    artifact_dir_raw = args.artifact_dir or os.getenv(DEFAULT_ARTIFACT_DIR_ENV)
    json_path = Path(args.json).resolve() if args.json else None
    markdown_path = Path(args.markdown).resolve() if args.markdown else None

    if not artifact_dir_raw and not (json_path and markdown_path):
        raise ArtifactError(
            "Provide --artifact-dir, set BIBER_AZURE_DEVOPS_ARTIFACT_DIR, or pass both --json and --markdown."
        )

    artifact_dir = Path(artifact_dir_raw).resolve() if artifact_dir_raw else json_path.parent
    if not artifact_dir.exists():
        raise ArtifactError(f"Artifact directory does not exist: {artifact_dir}")

    json_path = json_path or discover_artifact_file(artifact_dir, "biber-ai-review.json")
    markdown_path = markdown_path or discover_artifact_file(artifact_dir, "biber-ai-review.md")
    if not json_path or not json_path.is_file():
        raise ArtifactError("Could not find biber-ai-review.json in the artifact directory.")
    if not markdown_path or not markdown_path.is_file():
        raise ArtifactError("Could not find biber-ai-review.md in the artifact directory.")
    return artifact_dir, json_path, markdown_path


def leak_counts(*, summary_text: str, markdown_text: str) -> list[dict[str, Any]]:
    combined = summary_text + "\n" + markdown_text
    leaks: list[dict[str, Any]] = []
    for name, pattern in SECRET_LEAK_PATTERNS:
        count = len(pattern.findall(combined))
        leaks.append({"name": name, "count": count})
    return leaks


def validate_artifact(
    *,
    artifact_dir: Path,
    json_path: Path,
    markdown_path: Path,
    allow_non_fixture: bool,
    allow_posted_comment: bool,
) -> dict[str, Any]:
    summary_text = read_text(json_path)
    markdown_text = read_text(markdown_path)
    summary = read_json(json_path)
    comment_status = summary.get("comment_status") if isinstance(summary.get("comment_status"), dict) else {}
    changed_paths = summary.get("changed_paths") if isinstance(summary.get("changed_paths"), list) else []
    changed_paths = [str(path).replace("\\", "/") for path in changed_paths]
    leaks = leak_counts(summary_text=summary_text, markdown_text=markdown_text)
    leak_total = sum(item["count"] for item in leaks)

    azure_comment_request_sent = bool(summary.get("azure_comment_request_sent"))
    comment_posted = bool(comment_status.get("posted"))
    dry_run_mode = comment_status.get("mode") == "dry-run"
    fixture_present = EXPECTED_FIXTURE_PATH in changed_paths
    redaction_count = int(summary.get("secret_like_values_redacted") or 0)

    checks = [
        check(json_path.is_file(), "json_artifact_exists", str(json_path)),
        check(markdown_path.is_file(), "markdown_artifact_exists", str(markdown_path)),
        check(summary.get("source") == EXPECTED_SOURCE, "source_is_pr_review", str(summary.get("source"))),
        check(summary.get("ok") is True, "review_summary_ok"),
        check(str(summary.get("model") or "").startswith("biber-"), "model_is_biber_scoped", str(summary.get("model") or "")),
        check(summary.get("mentor_used") is False, "mentor_disabled"),
        check(summary.get("training_allowed") is False, "training_disabled"),
        check(summary.get("github_request_sent") is False, "github_not_called"),
        check(summary.get("api_key_included") is False, "api_key_not_included"),
        check(summary.get("azure_token_included") is False, "azure_token_not_included"),
        check((not azure_comment_request_sent) or allow_posted_comment, "azure_comment_request_not_sent"),
        check((not comment_posted) or allow_posted_comment, "azure_comment_not_posted"),
        check(dry_run_mode or allow_posted_comment, "comment_mode_dry_run", str(comment_status.get("mode"))),
        check(redaction_count >= 1 or allow_non_fixture, "secret_like_values_redacted", str(redaction_count)),
        check(fixture_present or allow_non_fixture, "fixture_changed_path_present", ",".join(changed_paths[:5])),
        check("## BIBER AI Review" in markdown_text, "markdown_has_biber_header"),
        check("OpenAI mentor:** `disabled`" in markdown_text or "OpenAI mentor: `disabled`" in markdown_text, "markdown_mentor_disabled"),
        check("[REDACTED_BIBER_SECRET]" in markdown_text or allow_non_fixture, "markdown_contains_redaction_marker"),
        check("not an automatic merge approval" in markdown_text, "markdown_human_review_only"),
        check(leak_total == 0, "no_raw_secret_markers", json.dumps(leaks, sort_keys=True)),
    ]
    failed = [item for item in checks if not item["ok"]]
    return {
        "source": "biber_azure_devops_live_artifact_acceptance",
        "ok": not failed,
        "status": "accepted" if not failed else "failed",
        "artifact_dir": str(artifact_dir),
        "json_artifact": str(json_path),
        "markdown_artifact": str(markdown_path),
        "api_required": False,
        "azure_devops_request_sent": False,
        "biber_request_sent": False,
        "external_network_required": False,
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "checked_artifact_source": summary.get("source"),
        "checked_artifact_api_required": bool(summary.get("api_required")),
        "checked_artifact_biber_request_sent": bool(summary.get("biber_request_sent")),
        "checked_artifact_external_network_required": bool(summary.get("external_network_required")),
        "checked_artifact_comment_status": comment_status,
        "checked_artifact_changed_paths": changed_paths[:40],
        "secret_leak_counts": leaks,
        "first_run_safe_to_show": not failed and not allow_posted_comment,
        "checks": checks,
        "failed": failed,
        "next_steps": [
            "If this was a downloaded Azure DevOps artifact, it is safe to review in the demo when ok=true.",
            "Keep commentMode=dry-run until this acceptance check passes on the disposable PR artifact.",
            "Do not enable comment posting until a separate explicit post-comment test is approved.",
        ],
    }


def self_test_artifact() -> tuple[Path, dict[str, Any]]:
    temp_dir = Path(tempfile.mkdtemp(prefix="biber-azdo-artifact-acceptance-"))
    mock_response = temp_dir / "mock-biber-response.json"
    write_json(
        mock_response,
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "\n".join(
                            [
                                "### Summary",
                                "The fixture weakens refund validation and logs a token-like value.",
                                "### Risk level",
                                "High risk until validation and logging are fixed.",
                                "### Correctness risks",
                                "Zero-amount refunds are no longer rejected.",
                                "### Security/privacy risks",
                                "Token-like data must stay redacted and out of logs.",
                                "### Tests to run or add",
                                "Run the refund-policy unittest and add a redaction assertion.",
                                "### Reviewer checklist",
                                "Confirm the validation guard and logging behavior.",
                                "### Merge recommendation",
                                "Do not merge until the fixture regressions are fixed.",
                            ]
                        ),
                    }
                }
            ],
            "usage": {"prompt_tokens": 80, "completion_tokens": 150, "total_tokens": 230},
        },
    )
    output_json = temp_dir / "biber-ai-review.json"
    output_md = temp_dir / "biber-ai-review.md"
    command = [
        sys.executable,
        str(PR_REVIEW_SCRIPT),
        "--repo-root",
        str(ROOT),
        "--mock-diff-file",
        str(FIXTURE_PATCH),
        "--mock-biber-response-file",
        str(mock_response),
        "--comment-mode",
        "dry-run",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]
    completed = subprocess.run(
        command,
        cwd=str(temp_dir),
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    return temp_dir, {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_preview": completed.stdout[:1000],
        "stderr_preview": completed.stderr[:1000],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", help="Downloaded/published biber-ai-review artifact directory.")
    parser.add_argument("--json", help="Explicit biber-ai-review.json path.")
    parser.add_argument("--markdown", help="Explicit biber-ai-review.md path.")
    parser.add_argument("--allow-non-fixture", action="store_true", help="Do not require the checked-in demo fixture path/redaction marker.")
    parser.add_argument("--allow-posted-comment", action="store_true", help="Accept a future commentMode=post artifact. Do not use for first dry-run.")
    parser.add_argument("--self-test", action="store_true", help="Generate a mock PR review artifact locally, then validate it.")
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    self_test = None
    try:
        if args.self_test:
            artifact_dir, self_test = self_test_artifact()
            if self_test["exit_code"] != 0:
                result = {
                    "source": "biber_azure_devops_live_artifact_acceptance",
                    "ok": False,
                    "status": "self_test_generation_failed",
                    "api_required": False,
                    "azure_devops_request_sent": False,
                    "biber_request_sent": False,
                    "external_network_required": False,
                    "github_request_sent": False,
                    "gpu_required": False,
                    "mentor_used": False,
                    "training_allowed": False,
                    "artifact_dir": str(artifact_dir),
                    "self_test_generation": self_test,
                    "failed": [check(False, "self_test_pr_review_generation")],
                }
            else:
                result = validate_artifact(
                    artifact_dir=artifact_dir,
                    json_path=artifact_dir / "biber-ai-review.json",
                    markdown_path=artifact_dir / "biber-ai-review.md",
                    allow_non_fixture=args.allow_non_fixture,
                    allow_posted_comment=args.allow_posted_comment,
                )
                result["self_test_generation"] = self_test
                result["self_test"] = True
        else:
            artifact_dir, json_path, markdown_path = resolve_artifact_paths(args)
            result = validate_artifact(
                artifact_dir=artifact_dir,
                json_path=json_path,
                markdown_path=markdown_path,
                allow_non_fixture=args.allow_non_fixture,
                allow_posted_comment=args.allow_posted_comment,
            )
            result["self_test"] = False
    except ArtifactError as exc:
        result = {
            "source": "biber_azure_devops_live_artifact_acceptance",
            "ok": False,
            "status": "blocked_missing_artifact",
            "api_required": False,
            "azure_devops_request_sent": False,
            "biber_request_sent": False,
            "external_network_required": False,
            "github_request_sent": False,
            "gpu_required": False,
            "mentor_used": False,
            "training_allowed": False,
            "error": str(exc),
            "failed": [check(False, "artifact_input_available", str(exc))],
        }

    if args.output:
        write_json(Path(args.output), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
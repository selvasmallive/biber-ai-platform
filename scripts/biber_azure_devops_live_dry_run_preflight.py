#!/usr/bin/env python3
"""Offline/live-gated preflight for the first BIBER Azure DevOps dry-run.

Default mode is local/offline only. It verifies the repo-side demo assets and
reports the human/live inputs still needed before a real Azure DevOps run.
Use --probe-api only when intentionally testing the public BIBER /v1/models
endpoint with a user-scoped key.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "examples" / "azure_devops_extension"
PIPELINE_ROOT = ROOT / "examples" / "azure_devops_pipeline"
DEMO_FIXTURE_ROOT = ROOT / "examples" / "azure_devops_demo_fixture"
DOCS = ROOT / "docs"
DEFAULT_BASE_URL = "https://api.beaverapi.com/v1"
DEFAULT_MODEL = "biber-dev-core-v1"
REQUIRED_PACKAGE_SCRIPTS = [
    "validate",
    "validate:panel",
    "validate:pipeline",
    "validate:conference",
    "validate:contract",
    "validate:wrapper",
    "demo:offline",
    "package",
]
REQUIRED_DOCS = [
    "BIBER_AZURE_DEVOPS_LIVE_DRY_RUN.md",
    "BIBER_AZURE_DEVOPS_DEMO_RUNBOOK.md",
    "BIBER_AZURE_DEVOPS_PRIVATE_PUBLISH.md",
    "BIBER_AZURE_DEVOPS_CONFERENCE_TALK.md",
]
REQUIRED_DEMO_FIXTURE = [
    "README.md",
    "src/refund_policy.py",
    "tests/test_refund_policy.py",
    "patches/demo-pr-reviewable-change.diff",
]
REQUIRED_PIPELINES = {
    "script_pr": "biber-ai-pr-review.yml",
    "extension_task_pr": "biber-ai-extension-task-pr-review.yml",
    "commit_review": "biber-ai-commit-review.yml",
}
LIVE_INPUTS = [
    {
        "name": "BIBER_API_KEY",
        "description": "User-scoped BIBER key stored as a secret Azure Pipeline variable.",
        "required_for": ["script_pr", "extension_task_pr", "commit_review", "api_probe"],
    },
    {
        "name": "BIBER_AZURE_DEVOPS_TEST_REPO_URL",
        "description": "URL of the disposable Azure DevOps test repository or PR.",
        "required_for": ["script_pr", "extension_task_pr", "commit_review"],
    },
    {
        "name": "BIBER_AZURE_DEVOPS_PRIVATE_EXTENSION_INSTALLED",
        "description": "Set to yes only after the private VSIX is uploaded/shared/installed.",
        "required_for": ["extension_task_pr"],
    },
    {
        "name": "BIBER_AZURE_DEVOPS_OAUTH_TOKEN_ALLOWED",
        "description": "Set to yes only after pipeline OAuth token access is enabled for a test PR.",
        "required_for": ["future_comment_post_only"],
    },
]


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def newest_vsix() -> Path | None:
    candidates = [*EXTENSION_ROOT.glob("*.vsix"), *(EXTENSION_ROOT / "dist").glob("*.vsix")]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def zip_members(path: Path | None) -> list[str]:
    if not path or not path.is_file():
        return []
    try:
        with zipfile.ZipFile(path) as archive:
            return sorted(name.replace("\\", "/") for name in archive.namelist())
    except zipfile.BadZipFile:
        return []


def has_member_ending(members: list[str], expected: str) -> bool:
    expected = expected.replace("\\", "/")
    return any(member == expected or member.endswith("/" + expected) for member in members)


def normalize_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned:
        return DEFAULT_BASE_URL
    return cleaned


def bool_env(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "y", "on"}


def masked_presence(name: str) -> dict[str, Any]:
    value = os.getenv(name)
    return {
        "name": name,
        "present": bool(value),
        "truthy_yes": bool_env(name),
        "length": len(value) if value else 0,
    }


def pipeline_safety_checks(path: Path, *, expected_comment_mode: str, expect_token: bool) -> list[dict[str, Any]]:
    text = read_text(path)
    return [
        check(path.is_file(), f"pipeline_exists:{path.name}"),
        check("BIBER_API_KEY: $(BIBER_API_KEY)" in text, f"pipeline_key_from_secret:{path.name}"),
        check("OPENAI_API_KEY" not in text, f"pipeline_no_openai_key:{path.name}"),
        check("BIBER_ADMIN_API_KEY" not in text, f"pipeline_no_admin_key:{path.name}"),
        check("BIBER_TRAIN_APPROVED" not in text, f"pipeline_no_training:{path.name}"),
        check("Review with OpenAI mentor" not in text, f"pipeline_no_mentor_trigger:{path.name}"),
        check(f"commentMode: \"{expected_comment_mode}\"" in text or f"--comment-mode {expected_comment_mode}" in text, f"pipeline_comment_mode_{expected_comment_mode}:{path.name}"),
        check(("SYSTEM_ACCESSTOKEN" in text) is expect_token, f"pipeline_oauth_token_expected_{expect_token}:{path.name}"),
        check("https://api.beaverapi.com/v1" in text, f"pipeline_public_base_url:{path.name}"),
        check("biber-dev-core-v1" in text, f"pipeline_default_model:{path.name}"),
    ]


def probe_models(base_url: str, api_key: str | None, timeout_seconds: float) -> dict[str, Any]:
    url = normalize_base_url(base_url) + "/models"
    headers = {"User-Agent": "BIBER-AzureDevOps-LiveDryRun-Preflight/0.1"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        return {"ok": False, "url": url, "error": f"HTTP {exc.code}: {detail}"}
    except Exception as exc:  # noqa: BLE001 - smoke artifact should preserve the failure detail.
        return {"ok": False, "url": url, "error": str(exc)}
    model_ids = []
    data = parsed.get("data") if isinstance(parsed, dict) else None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                model_ids.append(item["id"])
    return {"ok": True, "url": url, "model_ids": model_ids[:20], "model_count": len(model_ids)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("BIBER_OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.getenv("BIBER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--api-key-env", default="BIBER_API_KEY")
    parser.add_argument("--probe-api", action="store_true", help="Intentionally call /v1/models.")
    parser.add_argument("--require-live-inputs", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args()

    base_url = normalize_base_url(args.base_url)
    package_json = read_json(EXTENSION_ROOT / "package.json")
    manifest = read_json(EXTENSION_ROOT / "vss-extension.json")
    task_json = read_json(EXTENSION_ROOT / "tasks" / "biber-ai-pr-review" / "v1" / "task.json")
    live_values = {item["name"]: masked_presence(item["name"]) for item in LIVE_INPUTS}
    vsix = newest_vsix()
    vsix_members = zip_members(vsix)

    checks: list[dict[str, Any]] = []
    checks.extend(check((DOCS / name).is_file(), f"doc_exists:{name}") for name in REQUIRED_DOCS)
    checks.extend(
        check((PIPELINE_ROOT / name).is_file(), f"pipeline_file_exists:{label}")
        for label, name in REQUIRED_PIPELINES.items()
    )
    checks.extend(
        check((DEMO_FIXTURE_ROOT / name).is_file(), f"demo_fixture_file_exists:{name}")
        for name in REQUIRED_DEMO_FIXTURE
    )
    fixture_text = read_text(DEMO_FIXTURE_ROOT / "README.md") + "\n" + read_text(
        DEMO_FIXTURE_ROOT / "patches" / "demo-pr-reviewable-change.diff"
    )
    checks.append(check("commentMode=dry-run" in fixture_text, "demo_fixture_dry_run_guidance"))
    checks.append(check("FAKE_DEMO_TOKEN_DO_NOT_USE" in fixture_text, "demo_fixture_fake_token_marker"))
    checks.append(check("BIBER_ADMIN_API_KEY" not in fixture_text, "demo_fixture_no_admin_key"))
    checks.append(check("OPENAI_API_KEY" not in fixture_text, "demo_fixture_no_openai_key"))
    scripts = package_json.get("scripts") if isinstance(package_json.get("scripts"), dict) else {}
    checks.extend(check(name in scripts, f"package_script:{name}") for name in REQUIRED_PACKAGE_SCRIPTS)
    checks.append(check(manifest.get("public") is False, "manifest_private_release_default"))
    checks.append(check(manifest.get("publisher") == "flat-electronics-canada", "manifest_publisher"))
    checks.append(check(manifest.get("id") == "biber-ai-azure-devops", "manifest_id"))
    checks.append(check(bool(task_json.get("execution", {}).get("Node20_1", {}).get("target")), "task_node20_handler"))
    checks.append(check(vsix is not None and vsix.is_file(), "vsix_present"))
    checks.append(check(vsix.stat().st_size > 100_000 if vsix else False, "vsix_nontrivial_size"))
    checks.append(check(has_member_ending(vsix_members, "extension.vsixmanifest"), "vsix_has_manifest"))
    checks.append(check(has_member_ending(vsix_members, "tasks/biber-ai-pr-review/v1/task.json"), "vsix_has_task"))
    checks.append(check(has_member_ending(vsix_members, "static/main.js"), "vsix_has_panel_script"))
    checks.append(check(not any("node_modules/" in member for member in vsix_members), "vsix_excludes_node_modules"))
    checks.extend(
        pipeline_safety_checks(PIPELINE_ROOT / "biber-ai-pr-review.yml", expected_comment_mode="dry-run", expect_token=True)
    )
    checks.extend(
        pipeline_safety_checks(
            PIPELINE_ROOT / "biber-ai-extension-task-pr-review.yml",
            expected_comment_mode="dry-run",
            expect_token=True,
        )
    )
    checks.extend(
        pipeline_safety_checks(PIPELINE_ROOT / "biber-ai-commit-review.yml", expected_comment_mode="none", expect_token=False)
    )
    checks.append(check(base_url.startswith("https://"), "base_url_https"))
    checks.append(check("127.0.0.1" not in base_url and "localhost" not in base_url, "base_url_not_localhost"))
    checks.append(check(args.model == DEFAULT_MODEL or args.model.startswith("biber-"), "model_name_biber_scoped"))

    missing_live_inputs = [
        item
        for item in LIVE_INPUTS
        if item["name"] in {"BIBER_API_KEY", "BIBER_AZURE_DEVOPS_TEST_REPO_URL"}
        and not live_values[item["name"]]["present"]
    ]
    extension_installed = live_values["BIBER_AZURE_DEVOPS_PRIVATE_EXTENSION_INSTALLED"]["truthy_yes"]
    oauth_allowed = live_values["BIBER_AZURE_DEVOPS_OAUTH_TOKEN_ALLOWED"]["truthy_yes"]

    probe = None
    if args.probe_api:
        probe = probe_models(base_url, os.getenv(args.api_key_env), args.timeout_seconds)
        checks.append(check(bool(probe.get("ok")), "api_probe_models_ok", str(probe.get("error") or "")))

    local_failed = [item for item in checks if not item["ok"]]
    ready_for_script_pr_dry_run = not local_failed and not missing_live_inputs
    ready_for_installed_task_dry_run = ready_for_script_pr_dry_run and extension_installed
    ready_for_future_comment_post = ready_for_script_pr_dry_run and oauth_allowed

    next_steps = []
    if local_failed:
        next_steps.append("Fix failed local checks before using Azure DevOps.")
    if not live_values["BIBER_API_KEY"]["present"]:
        next_steps.append("Create or choose a user-scoped BIBER key and add it as secret pipeline variable BIBER_API_KEY.")
    if not live_values["BIBER_AZURE_DEVOPS_TEST_REPO_URL"]["present"]:
        next_steps.append("Choose a disposable Azure DevOps test repo/PR and record it as BIBER_AZURE_DEVOPS_TEST_REPO_URL for this preflight.")
    if not extension_installed:
        next_steps.append("Use the script-based PR pipeline first, or install/share the private VSIX before testing BiberAiPrReview@1.")
    if not oauth_allowed:
        next_steps.append("Keep commentMode=dry-run. Enable OAuth token access only later for a test PR comment-post demo.")
    if ready_for_script_pr_dry_run:
        next_steps.append("Run Path A from docs/BIBER_AZURE_DEVOPS_LIVE_DRY_RUN.md against the disposable test PR in dry-run mode.")

    status = "passed"
    if local_failed:
        status = "failed"
    elif not ready_for_script_pr_dry_run:
        status = "local_ready_waiting_for_live_inputs"
    elif ready_for_script_pr_dry_run and not ready_for_installed_task_dry_run:
        status = "ready_for_script_pr_dry_run"
    elif ready_for_installed_task_dry_run:
        status = "ready_for_installed_task_dry_run"

    result = {
        "source": "biber_azure_devops_live_dry_run_preflight",
        "ok": not local_failed and (not args.require_live_inputs or ready_for_script_pr_dry_run),
        "status": status,
        "api_required": bool(args.probe_api),
        "api_probe_sent": bool(args.probe_api),
        "azure_devops_request_sent": False,
        "external_network_required": bool(args.probe_api),
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "base_url": base_url,
        "model": args.model,
        "live_inputs": list(live_values.values()),
        "missing_live_inputs": [item["name"] for item in missing_live_inputs],
        "ready_for_script_pr_dry_run": ready_for_script_pr_dry_run,
        "ready_for_installed_task_dry_run": ready_for_installed_task_dry_run,
        "ready_for_future_comment_post": ready_for_future_comment_post,
        "probe": probe,
        "vsix": str(vsix) if vsix else None,
        "checks": checks,
        "failed": local_failed,
        "next_steps": next_steps,
    }
    body = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
    print(body, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

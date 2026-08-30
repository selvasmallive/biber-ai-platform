#!/usr/bin/env python3
"""Offline smoke test for the BIBER Azure DevOps PR review MVP."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AZURE_EXTENSION_ROOT = ROOT / "examples" / "azure_devops_extension"
PIPELINE_EXAMPLE = ROOT / "examples" / "azure_devops_pipeline" / "biber-ai-pr-review.yml"


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_script_smoke(tmp: Path) -> dict[str, Any]:
    diff_path = tmp / "mock.diff"
    response_path = tmp / "mock-biber-response.json"
    output_json = tmp / "biber-ai-review.json"
    output_md = tmp / "biber-ai-review.md"
    diff_path.write_text(
        """diff --git a/src/payments.ts b/src/payments.ts
--- a/src/payments.ts
+++ b/src/payments.ts
@@ -1,3 +1,6 @@
 export function approveTransfer(amount: number): boolean {
+  const token = "secret-value-for-redaction";
+  if (amount < 0) return true;
   return amount < 1000;
 }
""",
        encoding="utf-8",
    )
    response_path.write_text(
        json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": (
                                "### Summary\nThe transfer approval logic changed.\n\n"
                                "### Risk level\nHigh risk because negative amounts now pass.\n\n"
                                "### Correctness risks\nNegative transfers should be rejected.\n\n"
                                "### Security/privacy risks\nA secret-like value was present and must stay redacted.\n\n"
                                "### Tests to run or add\nAdd boundary tests for negative, zero, and high amounts.\n\n"
                                "### Reviewer checklist\nConfirm no secret value is committed.\n\n"
                                "### Merge recommendation\nDo not merge until the negative amount path is fixed."
                            ),
                        }
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "biber_azure_devops_pr_review.py"),
            "--repo-root",
            str(ROOT),
            "--base-url",
            "https://api.beaverapi.com/v1",
            "--model",
            "biber-dev-core-v1",
            "--mock-diff-file",
            str(diff_path),
            "--mock-biber-response-file",
            str(response_path),
            "--comment-mode",
            "dry-run",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        cwd=str(ROOT),
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    return {
        "ok": True,
        "payload": payload,
        "markdown": markdown,
        "stdout": completed.stdout,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args()

    manifest_path = AZURE_EXTENSION_ROOT / "vss-extension.json"
    task_path = AZURE_EXTENSION_ROOT / "tasks" / "biber-ai-pr-review" / "v1" / "task.json"
    task_script_path = (
        AZURE_EXTENSION_ROOT
        / "tasks"
        / "biber-ai-pr-review"
        / "v1"
        / "biber-ai-pr-review.js"
    )
    panel_html = AZURE_EXTENSION_ROOT / "static" / "index.html"
    panel_js = AZURE_EXTENSION_ROOT / "static" / "main.js"
    panel_css = AZURE_EXTENSION_ROOT / "static" / "styles.css"
    overview_path = AZURE_EXTENSION_ROOT / "overview.md"
    readme_path = AZURE_EXTENSION_ROOT / "README.md"
    icon_path = AZURE_EXTENSION_ROOT / "images" / "icon.png"
    task_icon_path = (
        AZURE_EXTENSION_ROOT
        / "tasks"
        / "biber-ai-pr-review"
        / "v1"
        / "icon.png"
    )
    script_path = ROOT / "scripts" / "biber_azure_devops_pr_review.py"
    src_config_path = ROOT / "src" / "biber_api" / "config.py"
    src_main_path = ROOT / "src" / "biber_api" / "main.py"
    app_config_path = ROOT / "app" / "config.py"
    app_main_path = ROOT / "app" / "main.py"

    checks: list[dict[str, Any]] = []
    for path in (
        manifest_path,
        task_path,
        panel_html,
        panel_js,
        panel_css,
        overview_path,
        readme_path,
        icon_path,
        task_icon_path,
        PIPELINE_EXAMPLE,
        script_path,
        task_script_path,
        src_config_path,
        src_main_path,
        app_config_path,
        app_main_path,
    ):
        checks.append(check(path.is_file(), f"exists:{path.relative_to(ROOT)}"))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    task = json.loads(task_path.read_text(encoding="utf-8"))
    panel_text = panel_html.read_text(encoding="utf-8") + "\n" + panel_js.read_text(encoding="utf-8")
    readme_text = readme_path.read_text(encoding="utf-8")
    script_text = script_path.read_text(encoding="utf-8")
    task_script_text = task_script_path.read_text(encoding="utf-8")
    pipeline_text = PIPELINE_EXAMPLE.read_text(encoding="utf-8")
    api_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (src_config_path, src_main_path, app_config_path, app_main_path)
    )

    contribution_ids = {
        item.get("id")
        for item in manifest.get("contributions", [])
        if isinstance(item, dict)
    }
    task_inputs = {
        item.get("name")
        for item in task.get("inputs", [])
        if isinstance(item, dict)
    }

    checks.extend(
        [
            check(manifest.get("id") == "biber-ai-azure-devops", "manifest:id"),
            check(manifest.get("publisher") == "flat-electronics-canada", "manifest:publisher"),
            check(manifest.get("version") == "0.1.0", "manifest:version"),
            check("Azure Repos" in manifest.get("categories", []), "manifest:azure_repos_category"),
            check("Azure Pipelines" in manifest.get("categories", []), "manifest:azure_pipelines_category"),
            check("Microsoft.VisualStudio.Services" in json.dumps(manifest), "manifest:target"),
            check("biber-ai-review-hub" in contribution_ids, "manifest:hub_contribution"),
            check("biber-ai-pr-review-task" in contribution_ids, "manifest:pipeline_task"),
            check("vso.code" in manifest.get("scopes", []), "manifest:code_scope"),
            check(task_icon_path.is_file(), "task:icon_png_exists"),
            check(
                bool(task.get("execution", {}).get("Node20_1", {}).get("target")),
                "task:node20_1_target",
            ),
            check("biberApiBaseUrl" in task_inputs, "task:base_url_input"),
            check("biberApiKey" not in task_inputs, "task:no_api_key_input"),
            check("commentMode" in task_inputs, "task:comment_mode_input"),
            check(
                "process.env.BIBER_API_KEY" in task_script_text,
                "task_script:api_key_from_env",
            ),
            check("SYSTEM_ACCESSTOKEN" in script_text, "script:system_access_token"),
            check('"use_mentor": False' in script_text, "script:mentor_disabled"),
            check("redact_secrets" in script_text, "script:redaction"),
            check("max-diff-bytes" in script_text, "script:bounded_diff"),
            check("/chat/completions" in script_text, "script:openai_compatible_endpoint"),
            check("pullRequests" in script_text and "threads" in script_text, "script:pr_thread_post"),
            check("BIBER_API_KEY" in pipeline_text, "pipeline:secret_biber_key"),
            check("System.AccessToken" in pipeline_text, "pipeline:system_access_token"),
            check("fetchDepth: 0" in pipeline_text, "pipeline:full_history_for_diff"),
            check("BIBER AI Review" in panel_text, "panel:title"),
            check("apiKey" in panel_text, "panel:api_key_field"),
            check("localStorage" not in panel_text, "panel:no_local_storage"),
            check("sessionStorage" not in panel_text, "panel:no_session_storage"),
            check("document.cookie" not in panel_text, "panel:no_cookie_storage"),
            check("Do not point" in readme_text, "readme:no_raw_vllm"),
            check("Cloudflare" in readme_text, "readme:public_edge"),
            check("CORS" in readme_text, "readme:cors_called_out"),
            check("BIBER_CORS_ALLOWED_ORIGINS" in readme_text, "readme:cors_origins_env"),
            check("BIBER_CORS_ALLOWED_ORIGIN_REGEX" in readme_text, "readme:cors_regex_env"),
            check("CORSMiddleware" in api_text, "api:cors_middleware"),
            check("cors_allowed_origins" in api_text, "api:cors_allowed_origins"),
            check("cors_allowed_origin_regex" in api_text, "api:cors_origin_regex"),
            check("azure_devops_extension_panel" in api_text, "api:capabilities_azure_panel"),
        ]
    )

    with tempfile.TemporaryDirectory(prefix="biber-azure-devops-smoke-") as tmp_name:
        smoke = run_script_smoke(Path(tmp_name))
    checks.append(check(smoke.get("ok") is True, "script:offline_mock_run"))
    if smoke.get("ok") is True:
        payload = smoke["payload"]
        markdown = smoke["markdown"]
        checks.extend(
            [
                check(payload.get("ok") is True, "script:payload_ok"),
                check(payload.get("biber_request_sent") is False, "script:mock_no_biber_request"),
                check(payload.get("azure_comment_request_sent") is False, "script:dry_run_no_comment"),
                check(payload.get("mentor_used") is False, "script:mentor_unused"),
                check(payload.get("training_allowed") is False, "script:training_disallowed"),
                check(payload.get("api_key_included") is False, "script:no_api_key_artifact"),
                check(payload.get("risk_level") == "high", "script:risk_high_from_review"),
                check(payload.get("secret_like_values_redacted", 0) >= 1, "script:redaction_count"),
                check("secret-value-for-redaction" not in markdown, "script:markdown_secret_redacted"),
                check("BIBER AI Review" in markdown, "script:markdown_comment_header"),
            ]
        )
    else:
        checks.append(check(False, "script:offline_mock_detail", json.dumps(smoke)[:1000]))

    ok = all(item["ok"] for item in checks)
    result = {
        "source": "biber_azure_devops_review_smoke",
        "ok": ok,
        "api_required": False,
        "external_network_required": False,
        "github_request_sent": False,
        "mentor_used": False,
        "training_allowed": False,
        "extension_root": str(AZURE_EXTENSION_ROOT),
        "pipeline_example": str(PIPELINE_EXAMPLE),
        "checks": checks,
        "failed": [item for item in checks if not item["ok"]],
    }
    if args.output:
        write_json(Path(args.output), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

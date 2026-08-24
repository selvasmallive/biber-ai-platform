#!/usr/bin/env python3
"""Offline guard for the BIBER VS Code extension MVP security contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "examples" / "vscode_extension"


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args()

    package_path = EXTENSION_ROOT / "package.json"
    package_lock_path = EXTENSION_ROOT / "package-lock.json"
    gitignore_path = EXTENSION_ROOT / ".gitignore"
    readme_path = EXTENSION_ROOT / "README.md"
    extension_path = EXTENSION_ROOT / "src" / "extension.ts"
    tsconfig_path = EXTENSION_ROOT / "tsconfig.json"

    checks: list[dict[str, Any]] = []
    for path in (
        package_path,
        package_lock_path,
        gitignore_path,
        readme_path,
        extension_path,
        tsconfig_path,
    ):
        checks.append(check(path.is_file(), f"exists:{path.relative_to(ROOT)}"))

    package = json.loads(package_path.read_text(encoding="utf-8"))
    package_lock = json.loads(package_lock_path.read_text(encoding="utf-8"))
    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    commands = {
        item.get("command")
        for item in package.get("contributes", {}).get("commands", [])
        if isinstance(item, dict)
    }
    config_props = package.get("contributes", {}).get("configuration", {}).get(
        "properties", {}
    )
    dev_dependencies = package.get("devDependencies", {})
    extension_text = extension_path.read_text(encoding="utf-8")
    readme_text = readme_path.read_text(encoding="utf-8")

    checks.extend(
        [
            check("biber.setApiKey" in commands, "command:set_api_key"),
            check("biber.clearApiKey" in commands, "command:clear_api_key"),
            check("biber.testConnection" in commands, "command:test_connection"),
            check("biber.orchestrationPlan" in commands, "command:orchestration_plan"),
            check("biber.openaiBaseUrl" in config_props, "config:base_url"),
            check("biber.maxRequestsPerMinute" in config_props, "config:rate_limit"),
            check("biber.requestTimeoutMs" in config_props, "config:timeout"),
            check("biber.maxPromptChars" in config_props, "config:prompt_limit"),
            check("biber.maxChangedPaths" in config_props, "config:changed_path_limit"),
            check(
                package_lock.get("lockfileVersion") == 3,
                "package_lock:npm_lockfile_v3",
            ),
            check(
                dev_dependencies.get("@types/vscode") == "1.92.0",
                "dependency:vscode_types_pinned_to_engine",
            ),
            check("node_modules/" in gitignore_text, "gitignore:node_modules"),
            check("out/" in gitignore_text, "gitignore:out"),
            check("*.vsix" in gitignore_text, "gitignore:vsix"),
            check("context.secrets.store" in extension_text, "secret_storage_store"),
            check("context.secrets.get" in extension_text, "secret_storage_get"),
            check("Authorization" in extension_text, "bearer_auth_header"),
            check("checkRateLimit" in extension_text, "client_rate_limit"),
            check("inFlightRequest" in extension_text, "single_flight_guard"),
            check("AbortController" in extension_text, "request_timeout_abort"),
            check("assertAllowedBaseUrl" in extension_text, "https_or_localhost_guard"),
            check("sends_file_contents: false" in extension_text, "no_file_contents_mvp"),
            check("testConnection" in extension_text, "connection_test_command_handler"),
            check("/agent/capabilities" in extension_text, "capabilities_endpoint"),
            check("server_side_protections" in extension_text, "server_side_protection_summary"),
            check("/agent/orchestration/plan" in extension_text, "orchestration_endpoint"),
            check("SecretStorage" in readme_text, "readme_secret_storage"),
            check("rate limit" in readme_text.lower(), "readme_rate_limit"),
            check("single-flight" in readme_text.lower(), "readme_single_flight"),
            check("HTTPS" in readme_text, "readme_https"),
            check("Test API Connection" in readme_text, "readme_connection_test"),
            check(
                "Do not point the extension at the raw vLLM" in readme_text,
                "readme_no_raw_vllm",
            ),
        ]
    )

    forbidden_markers = [
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "console.log(apiKey",
        'workspace.getConfiguration().update("apiKey"',
    ]
    for marker in forbidden_markers:
        checks.append(check(marker not in extension_text, f"forbidden_absent:{marker}"))

    ok = all(item["ok"] for item in checks)
    result = {
        "source": "biber_vscode_extension_contract_smoke",
        "ok": ok,
        "api_required": False,
        "external_network_required": False,
        "github_request_sent": False,
        "mentor_used": False,
        "training_allowed": False,
        "extension_root": str(EXTENSION_ROOT),
        "checks": checks,
        "failed": [item for item in checks if not item["ok"]],
    }
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

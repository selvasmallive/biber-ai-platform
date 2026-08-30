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
    vscodeignore_path = EXTENSION_ROOT / ".vscodeignore"
    icon_path = EXTENSION_ROOT / "media" / "icon.png"
    activity_icon_path = EXTENSION_ROOT / "media" / "activity-icon.svg"
    license_path = EXTENSION_ROOT / "LICENSE.md"
    changelog_path = EXTENSION_ROOT / "CHANGELOG.md"
    readme_path = EXTENSION_ROOT / "README.md"
    extension_path = EXTENSION_ROOT / "src" / "extension.ts"
    tsconfig_path = EXTENSION_ROOT / "tsconfig.json"

    checks: list[dict[str, Any]] = []
    for path in (
        package_path,
        package_lock_path,
        gitignore_path,
        vscodeignore_path,
        icon_path,
        activity_icon_path,
        license_path,
        changelog_path,
        readme_path,
        extension_path,
        tsconfig_path,
    ):
        checks.append(check(path.is_file(), f"exists:{path.relative_to(ROOT)}"))

    package = json.loads(package_path.read_text(encoding="utf-8"))
    package_lock = json.loads(package_lock_path.read_text(encoding="utf-8"))
    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    vscodeignore_text = vscodeignore_path.read_text(encoding="utf-8")
    commands = {
        item.get("command")
        for item in package.get("contributes", {}).get("commands", [])
        if isinstance(item, dict)
    }
    activation_events = set(package.get("activationEvents", []))
    contributes = package.get("contributes", {})
    activitybar = (
        contributes.get("viewsContainers", {})
        .get("activitybar", [])
    )
    views = contributes.get("views", {})
    views_welcome = contributes.get("viewsWelcome", [])
    view_title_menus = contributes.get("menus", {}).get("view/title", [])
    config_props = package.get("contributes", {}).get("configuration", {}).get(
        "properties", {}
    )
    dev_dependencies = package.get("devDependencies", {})
    scripts = package.get("scripts", {})
    extension_text = extension_path.read_text(encoding="utf-8")
    readme_text = readme_path.read_text(encoding="utf-8")

    checks.extend(
        [
            check(package.get("name") == "biber-ai-assistant", "package_name_marketplace_ready"),
            check(
                package.get("publisher") == "flat-electronics-canada",
                "publisher_flat_electronics_canada",
            ),
            check(package.get("displayName") == "BIBER AI Assistant", "display_name_public"),
            check(package.get("pricing") == "Free", "pricing_free"),
            check(package.get("icon") == "media/icon.png", "icon_declared_png"),
            check(icon_path.is_file(), "icon_file_exists"),
            check(icon_path.suffix.lower() == ".png", "icon_is_png"),
            check(activity_icon_path.is_file(), "activity_icon_file_exists"),
            check(activity_icon_path.suffix.lower() == ".svg", "activity_icon_is_svg"),
            check(package.get("license") == "SEE LICENSE IN LICENSE.md", "license_declared"),
            check("Machine Learning" in package.get("categories", []), "category_machine_learning"),
            check("repository" in package, "repository_declared"),
            check("bugs" in package, "bugs_declared"),
            check("capabilities" in package, "capabilities_declared"),
            check("vsce package" in scripts.get("package", ""), "script_package_vsce"),
            check("vsce publish" in scripts.get("publish", ""), "script_publish_vsce"),
            check("onStartupFinished" in activation_events, "activation:on_startup_finished"),
            check("onView:biber.changeAgentView" in activation_events, "activation:on_biber_view"),
            check("biber.openChat" in commands, "command:open_chat"),
            check("biber.openSetup" in commands, "command:open_setup"),
            check("biber.setApiKey" in commands, "command:set_api_key"),
            check("biber.clearApiKey" in commands, "command:clear_api_key"),
            check("biber.testConnection" in commands, "command:test_connection"),
            check("biber.orchestrationPlan" in commands, "command:orchestration_plan"),
            check("biber.openOutput" in commands, "command:open_output"),
            check("biber.refreshSidebar" in commands, "command:refresh_sidebar"),
            check(
                any(
                    isinstance(item, dict)
                    and item.get("id") == "biber"
                    and item.get("title") == "BIBER"
                    and item.get("icon") == "media/activity-icon.svg"
                    for item in activitybar
                ),
                "view_container:biber_activitybar",
            ),
            check(
                any(
                    isinstance(item, dict)
                    and item.get("id") == "biber.changeAgentView"
                    and item.get("name") == "Chat Agent"
                    and item.get("type") == "webview"
                    for item in views.get("biber", [])
                ),
                "view:biber_chat_agent_webview",
            ),
            check(
                any(
                    isinstance(item, dict)
                    and item.get("view") == "biber.changeAgentView"
                    and "Open Chat Agent" in item.get("contents", "")
                    for item in views_welcome
                ),
                "view_welcome:open_chat_link",
            ),
            check(
                any(
                    isinstance(item, dict)
                    and item.get("command") == "biber.refreshSidebar"
                    for item in view_title_menus
                ),
                "view_title_menu:refresh",
            ),
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
            check("dist/" in gitignore_text, "gitignore:dist"),
            check("*.vsix" in gitignore_text, "gitignore:vsix"),
            check("node_modules/**" in vscodeignore_text, "vscodeignore:node_modules"),
            check("src/**" in vscodeignore_text, "vscodeignore:src"),
            check("dist/**" in vscodeignore_text, "vscodeignore:dist"),
            check("out/**/*.map" in vscodeignore_text, "vscodeignore:source_maps"),
            check(".gitignore" in vscodeignore_text, "vscodeignore:gitignore"),
            check(
                "media/**" not in vscodeignore_text
                and "media/icon.png" not in vscodeignore_text,
                "vscodeignore:icon_not_excluded",
            ),
            check("context.secrets.store" in extension_text, "secret_storage_store"),
            check("context.secrets.get" in extension_text, "secret_storage_get"),
            check("Authorization" in extension_text, "bearer_auth_header"),
            check("User-Agent" in extension_text, "api_client_user_agent"),
            check("X-BIBER-Client" in extension_text, "api_client_identity_header"),
            check("checkRateLimit" in extension_text, "client_rate_limit"),
            check("inFlightRequest" in extension_text, "single_flight_guard"),
            check("AbortController" in extension_text, "request_timeout_abort"),
            check("assertAllowedBaseUrl" in extension_text, "https_or_localhost_guard"),
            check("createStatusBarItem" in extension_text, "status_bar_visible_entry"),
            check("biber.openChat" in extension_text, "open_chat_command_handler"),
            check("registerWebviewViewProvider" in extension_text, "activity_view_webview_provider"),
            check("BiberChatViewProvider" in extension_text, "chat_agent_webview_provider"),
            check("retainContextWhenHidden" in extension_text, "webview_retains_context_when_hidden"),
            check("Content-Security-Policy" in extension_text, "webview_content_security_policy"),
            check("acquireVsCodeApi" in extension_text, "webview_message_bridge"),
            check("saveSetupFromView" in extension_text, "webview_inline_setup_save"),
            check("showQuickPick<SetupEndpointPick>" in extension_text, "guided_setup_endpoint_pick"),
            check("promptAndStoreApiKey" in extension_text, "guided_setup_secret_storage"),
            check("offerNextAction" in extension_text, "guided_setup_continues_without_single_flight"),
            check("Ask BIBER" in extension_text, "webview_ask_biber_button"),
            check("BIBER Change Agent" in extension_text, "change_agent_prompt_title"),
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
            check("Activity Bar" in readme_text, "readme_activity_bar"),
            check("Chat Agent" in readme_text, "readme_chat_agent"),
            check("Setup API Connection" in readme_text, "readme_setup_flow"),
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

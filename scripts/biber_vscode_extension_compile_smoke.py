#!/usr/bin/env python3
"""Run the optional VS Code extension npm install/compile smoke."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "examples" / "vscode_extension"


def run_command(command: list[str], timeout_seconds: float) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=EXTENSION_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "command": command,
            "cwd": str(EXTENSION_ROOT),
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
            "cwd": str(EXTENSION_ROOT),
            "executed": True,
            "timed_out": True,
            "exit_code": None,
            "ok": False,
            "stdout": (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "",
        }


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument(
        "--allow-missing-npm",
        action="store_true",
        help="Write a blocked artifact and exit 0 when npm is unavailable.",
    )
    parser.add_argument(
        "--skip-npm-ci",
        action="store_true",
        help="Use existing node_modules and run compile only. Useful when OneDrive locks generated npm files.",
    )
    args = parser.parse_args()

    npm = shutil.which("npm")
    checks = [
        check(EXTENSION_ROOT.is_dir(), "extension_root_exists"),
        check((EXTENSION_ROOT / "package.json").is_file(), "package_json_exists"),
        check((EXTENSION_ROOT / "package-lock.json").is_file(), "package_lock_exists"),
        check(bool(npm), "npm_available"),
    ]
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    notes: list[str] = []

    if not npm:
        blockers.append("npm_not_available")
    else:
        if not args.skip_npm_ci:
            commands.append(run_command([npm, "ci"], args.timeout_seconds))
        else:
            notes.append("npm_ci_skipped")
        if args.skip_npm_ci or commands[-1]["ok"]:
            commands.append(run_command([npm, "run", "compile"], args.timeout_seconds))

    extension_js = EXTENSION_ROOT / "out" / "extension.js"
    extension_map = EXTENSION_ROOT / "out" / "extension.js.map"
    if npm and all(command["ok"] for command in commands):
        extension_text = extension_js.read_text(encoding="utf-8") if extension_js.is_file() else ""
        checks.extend(
            [
                check(extension_js.is_file(), "compiled_extension_js_exists"),
                check(extension_map.is_file(), "compiled_source_map_exists"),
                check("biber.testConnection" in extension_text, "compiled_test_connection"),
                check("biber.openSetup" in extension_text, "compiled_setup_command"),
                check("biber.openOutput" in extension_text, "compiled_open_output_command"),
                check("registerTreeDataProvider" in extension_text, "compiled_tree_view"),
                check("createStatusBarItem" in extension_text, "compiled_status_bar"),
                check("/agent/capabilities" in extension_text, "compiled_capabilities_endpoint"),
                check(
                    "/agent/orchestration/plan" in extension_text,
                    "compiled_orchestration_endpoint",
                ),
                check("User-Agent" in extension_text, "compiled_api_client_user_agent"),
                check("X-BIBER-Client" in extension_text, "compiled_api_client_identity_header"),
            ]
        )

    ok = (
        all(item["ok"] for item in checks)
        and bool(commands)
        and all(command["ok"] for command in commands)
        and not blockers
    )
    result = {
        "source": "biber_vscode_extension_compile_smoke",
        "ok": ok,
        "status": "passed" if ok else ("blocked" if blockers else "failed"),
        "api_required": False,
        "external_network_required": True,
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "extension_root": str(EXTENSION_ROOT),
        "npm": npm,
        "checks": checks,
        "commands": commands,
        "blockers": blockers,
        "notes": notes,
        "failed": [
            item
            for item in checks
            if not item["ok"]
        ]
        + [
            {
                "name": "command:" + " ".join(command["command"]),
                "ok": False,
                "detail": command.get("stderr") or command.get("stdout") or "",
            }
            for command in commands
            if not command["ok"]
        ],
    }
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    if ok or (args.allow_missing_npm and blockers == ["npm_not_available"]):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

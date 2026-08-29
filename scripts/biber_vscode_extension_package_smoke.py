#!/usr/bin/env python3
"""Package and install-test the BIBER VS Code extension VSIX."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "examples" / "vscode_extension"
EXPECTED_EXTENSION_ID = "flat-electronics-canada.biber-ai-assistant"
EXPECTED_ICON_SOURCE = "media/icon.png"
EXPECTED_ICON_PACKAGE_PATH = "extension/media/icon.png"


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "command": command,
            "cwd": str(cwd),
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
            "cwd": str(cwd),
            "executed": True,
            "timed_out": True,
            "exit_code": None,
            "ok": False,
            "stdout": (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "",
        }


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def read_package_json() -> dict[str, Any]:
    return json.loads((EXTENSION_ROOT / "package.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--skip-install-test",
        action="store_true",
        help="Package only; do not run the isolated VS Code install test.",
    )
    parser.add_argument(
        "--allow-missing-code",
        action="store_true",
        help="Write a blocked install-test artifact and exit 0 when the code CLI is unavailable.",
    )
    parser.add_argument(
        "--skip-npm-ci",
        action="store_true",
        help="Use existing node_modules and run compile/package only. Useful when OneDrive locks generated npm files.",
    )
    args = parser.parse_args()

    npm = shutil.which("npm")
    code = shutil.which("code")
    package = read_package_json() if (EXTENSION_ROOT / "package.json").is_file() else {}
    package_icon = package.get("icon")
    icon_path = (
        EXTENSION_ROOT / package_icon
        if isinstance(package_icon, str)
        else EXTENSION_ROOT / "__missing_icon__"
    )
    package_name = str(package.get("name") or "biber-ai-assistant")
    package_version = str(package.get("version") or "0.0.0")
    expected_vsix_name = f"{package_name}-{package_version}.vsix"
    dist_dir = EXTENSION_ROOT / "dist"
    vsix_path = dist_dir / expected_vsix_name
    dist_dir.mkdir(parents=True, exist_ok=True)
    if vsix_path.exists():
        vsix_path.unlink()

    checks = [
        check(EXTENSION_ROOT.is_dir(), "extension_root_exists"),
        check((EXTENSION_ROOT / "package.json").is_file(), "package_json_exists"),
        check((EXTENSION_ROOT / "package-lock.json").is_file(), "package_lock_exists"),
        check((EXTENSION_ROOT / ".vscodeignore").is_file(), "vscodeignore_exists"),
        check((EXTENSION_ROOT / "LICENSE.md").is_file(), "license_exists"),
        check(package.get("publisher") == "flat-electronics-canada", "publisher_matches_marketplace"),
        check(package.get("name") == "biber-ai-assistant", "name_matches_marketplace"),
        check(package_icon == EXPECTED_ICON_SOURCE, "icon_declared_png"),
        check(icon_path.is_file(), "icon_file_exists"),
        check(icon_path.suffix.lower() == ".png", "icon_is_png"),
        check(bool(npm), "npm_available"),
    ]
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    notes: list[str] = []

    if not npm:
        blockers.append("npm_not_available")
    else:
        if not args.skip_npm_ci:
            commands.append(run_command([npm, "ci"], cwd=EXTENSION_ROOT, timeout_seconds=args.timeout_seconds))
        else:
            notes.append("npm_ci_skipped")
        if args.skip_npm_ci or commands[-1]["ok"]:
            commands.append(
                run_command([npm, "run", "compile"], cwd=EXTENSION_ROOT, timeout_seconds=args.timeout_seconds)
            )
        if commands and commands[-1]["ok"]:
            commands.append(
                run_command(
                    [npm, "run", "package", "--", "--out", str(vsix_path)],
                    cwd=EXTENSION_ROOT,
                    timeout_seconds=args.timeout_seconds,
                )
            )

    vsix_members: list[str] = []
    if vsix_path.is_file():
        try:
            with zipfile.ZipFile(vsix_path) as archive:
                vsix_members = archive.namelist()
        except zipfile.BadZipFile:
            vsix_members = []

    checks.extend(
        [
            check(vsix_path.is_file(), "vsix_created", str(vsix_path)),
            check(vsix_path.stat().st_size > 0 if vsix_path.is_file() else False, "vsix_nonempty"),
            check(
                EXPECTED_ICON_PACKAGE_PATH in vsix_members,
                "vsix_contains_marketplace_icon",
                EXPECTED_ICON_PACKAGE_PATH,
            ),
        ]
    )

    install_commands: list[dict[str, Any]] = []
    installed_extensions = ""
    if args.skip_install_test:
        blockers.append("install_test_skipped")
    elif not code:
        blockers.append("code_cli_not_available")
    elif vsix_path.is_file():
        with tempfile.TemporaryDirectory(prefix="biber-vscode-extensions-") as extensions_dir, tempfile.TemporaryDirectory(
            prefix="biber-vscode-user-data-"
        ) as user_data_dir:
            install_commands.append(
                run_command(
                    [
                        code,
                        "--extensions-dir",
                        extensions_dir,
                        "--user-data-dir",
                        user_data_dir,
                        "--install-extension",
                        str(vsix_path),
                        "--force",
                    ],
                    cwd=EXTENSION_ROOT,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            install_commands.append(
                run_command(
                    [
                        code,
                        "--extensions-dir",
                        extensions_dir,
                        "--user-data-dir",
                        user_data_dir,
                        "--list-extensions",
                        "--show-versions",
                    ],
                    cwd=EXTENSION_ROOT,
                    timeout_seconds=args.timeout_seconds,
                )
            )
            installed_extensions = install_commands[-1].get("stdout", "")

    checks.extend(
        [
            check(bool(code) or args.skip_install_test, "code_cli_available_or_skipped"),
            check(
                args.skip_install_test
                or f"{EXPECTED_EXTENSION_ID}@{package.get('version')}" in installed_extensions,
                "isolated_install_lists_extension",
            ),
        ]
    )

    failed_commands = [command for command in [*commands, *install_commands] if not command["ok"]]
    ok = all(item["ok"] for item in checks) and not failed_commands and not blockers
    if args.allow_missing_code and blockers == ["code_cli_not_available"]:
        ok = False
    result = {
        "source": "biber_vscode_extension_package_smoke",
        "ok": ok,
        "status": "passed" if ok else ("blocked" if blockers and not failed_commands else "failed"),
        "api_required": False,
        "external_network_required": True,
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "extension_root": str(EXTENSION_ROOT),
        "extension_id": EXPECTED_EXTENSION_ID,
        "package_version": package_version,
        "expected_vsix_name": expected_vsix_name,
        "vsix_path": str(vsix_path),
        "vsix_members": vsix_members,
        "npm": npm,
        "code": code,
        "checks": checks,
        "commands": commands,
        "install_commands": install_commands,
        "blockers": blockers,
        "notes": notes,
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
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    if ok or (args.allow_missing_code and blockers == ["code_cli_not_available"]):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

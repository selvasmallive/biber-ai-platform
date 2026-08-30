#!/usr/bin/env python3
"""Package-check the BIBER Azure DevOps extension VSIX."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "examples" / "azure_devops_extension"
EXPECTED_MEMBERS = [
    "extension.vsomanifest",
    "extension.vsixmanifest",
    "overview.md",
    "images/icon.png",
    "static/index.html",
    "static/main.js",
    "static/styles.css",
    "tasks/biber-ai-pr-review/v1/task.json",
    "tasks/biber-ai-pr-review/v1/biber-ai-pr-review.js",
    "tasks/biber-ai-pr-review/v1/icon.png",
]


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def run_command(command: list[str], *, cwd: Path, timeout_seconds: float) -> dict[str, Any]:
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def remove_old_vsix() -> list[str]:
    removed: list[str] = []
    for path in [*EXTENSION_ROOT.glob("*.vsix"), *(EXTENSION_ROOT / "dist").glob("*.vsix")]:
        path.unlink()
        removed.append(str(path))
    return removed


def newest_vsix() -> Path | None:
    candidates = [*EXTENSION_ROOT.glob("*.vsix"), *(EXTENSION_ROOT / "dist").glob("*.vsix")]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def normalized_members(vsix_path: Path) -> list[str]:
    with zipfile.ZipFile(vsix_path) as archive:
        return sorted(name.replace("\\", "/") for name in archive.namelist())


def has_member_ending(members: list[str], expected_suffix: str) -> bool:
    expected = expected_suffix.replace("\\", "/")
    return any(member == expected or member.endswith("/" + expected) for member in members)


def archive_text_members(vsix_path: Path, members: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    with zipfile.ZipFile(vsix_path) as archive:
        for member in members:
            if not member.endswith((".json", ".md", ".html", ".js", ".css", ".yml", ".yaml")):
                continue
            try:
                texts[member] = archive.read(member).decode("utf-8", errors="replace")
            except KeyError:
                continue
    return texts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    parser.add_argument(
        "--skip-npm-install",
        action="store_true",
        help="Use existing node_modules/package-lock and run validation/package only.",
    )
    parser.add_argument(
        "--allow-missing-npm",
        action="store_true",
        help="Write a blocked artifact and exit 0 when npm is unavailable.",
    )
    args = parser.parse_args()

    npm = shutil.which("npm")
    package_path = EXTENSION_ROOT / "package.json"
    manifest_path = EXTENSION_ROOT / "vss-extension.json"
    task_path = EXTENSION_ROOT / "tasks" / "biber-ai-pr-review" / "v1" / "task.json"
    package = read_json(package_path) if package_path.is_file() else {}
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    task = read_json(task_path) if task_path.is_file() else {}

    checks: list[dict[str, Any]] = [
        check(EXTENSION_ROOT.is_dir(), "extension_root_exists"),
        check(package_path.is_file(), "package_json_exists"),
        check(manifest_path.is_file(), "manifest_exists"),
        check(task_path.is_file(), "task_json_exists"),
        check((EXTENSION_ROOT / "images" / "icon.png").is_file(), "marketplace_icon_exists"),
        check((task_path.parent / "icon.png").is_file(), "task_icon_exists"),
        check(package.get("name") == "biber-ai-azure-devops", "package_name"),
        check(package.get("private") is True, "package_private"),
        check(manifest.get("publisher") == "flat-electronics-canada", "manifest_publisher"),
        check(manifest.get("public") is False, "manifest_private_release"),
        check("Azure Repos" in manifest.get("categories", []), "manifest_azure_repos_category"),
        check("Azure Pipelines" in manifest.get("categories", []), "manifest_azure_pipelines_category"),
        check(bool(task.get("execution", {}).get("Node20_1", {}).get("target")), "task_node20_1"),
        check(bool(npm), "npm_available"),
    ]

    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    notes: list[str] = []
    removed_vsix: list[str] = []
    if not npm:
        blockers.append("npm_not_available")
    else:
        removed_vsix = remove_old_vsix()
        if args.skip_npm_install:
            notes.append("npm_install_skipped")
        elif (EXTENSION_ROOT / "package-lock.json").is_file():
            commands.append(
                run_command([npm, "ci"], cwd=EXTENSION_ROOT, timeout_seconds=args.timeout_seconds)
            )
        else:
            commands.append(
                run_command([npm, "install"], cwd=EXTENSION_ROOT, timeout_seconds=args.timeout_seconds)
            )
        if args.skip_npm_install or all(command["ok"] for command in commands):
            commands.append(
                run_command([npm, "run", "validate"], cwd=EXTENSION_ROOT, timeout_seconds=args.timeout_seconds)
            )
        if commands and commands[-1]["ok"]:
            commands.append(
                run_command([npm, "run", "package"], cwd=EXTENSION_ROOT, timeout_seconds=args.timeout_seconds)
            )

    package_lock = EXTENSION_ROOT / "package-lock.json"
    checks.append(check(package_lock.is_file(), "package_lock_exists"))

    vsix_path = newest_vsix()
    members: list[str] = []
    text_members: dict[str, str] = {}
    if vsix_path and vsix_path.is_file():
        try:
            members = normalized_members(vsix_path)
            text_members = archive_text_members(vsix_path, members)
        except zipfile.BadZipFile:
            members = []
            text_members = {}

    archive_text = "\n".join(text_members.values())
    checks.extend(
        [
            check(vsix_path is not None and vsix_path.is_file(), "vsix_created"),
            check(vsix_path.stat().st_size > 0 if vsix_path else False, "vsix_nonempty"),
            *[
                check(
                    has_member_ending(members, expected),
                    f"vsix_contains:{expected}",
                )
                for expected in EXPECTED_MEMBERS
            ],
            check(not any(".env" in member for member in members), "vsix_excludes_env_files"),
            check(not any("node_modules/" in member for member in members), "vsix_excludes_node_modules"),
            check("OPENAI_API_KEY=" not in archive_text, "vsix_no_openai_key_assignment"),
            check("BIBER_ADMIN_API_KEY=" not in archive_text, "vsix_no_admin_key_assignment"),
        ]
    )

    failed_commands = [command for command in commands if not command["ok"]]
    ok = all(item["ok"] for item in checks) and not failed_commands and not blockers
    status = "passed" if ok else ("blocked" if blockers and not failed_commands else "failed")
    if args.allow_missing_npm and blockers == ["npm_not_available"]:
        status = "blocked"

    result = {
        "source": "biber_azure_devops_extension_package_smoke",
        "ok": ok,
        "status": status,
        "api_required": False,
        "external_network_required": not args.skip_npm_install,
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "extension_root": str(EXTENSION_ROOT),
        "vsix_path": str(vsix_path) if vsix_path else None,
        "npm": npm,
        "removed_vsix": removed_vsix,
        "checks": checks,
        "commands": commands,
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
    if ok or (args.allow_missing_npm and blockers == ["npm_not_available"]):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

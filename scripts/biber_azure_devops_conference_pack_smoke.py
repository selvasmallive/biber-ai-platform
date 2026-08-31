#!/usr/bin/env python3
"""Offline readiness check for the BIBER Azure DevOps conference demo pack."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = ROOT / "examples" / "azure_devops_extension"
DOCS = ROOT / "docs"
PPTX = DOCS / "BIBER_Azure_DevOps_Private_Code_Review_Talk.pptx"
REQUIRED_DOCS = [
    DOCS / "BIBER_AZURE_DEVOPS_CONFERENCE_TALK.md",
    DOCS / "BIBER_AZURE_DEVOPS_CONFERENCE_SUBMISSION.md",
    DOCS / "BIBER_AZURE_DEVOPS_DEMO_RUNBOOK.md",
    DOCS / "BIBER_AZURE_DEVOPS_FIRST_RUN_QUICKSTART.md",
    DOCS / "BIBER_AZURE_DEVOPS_LIVE_DRY_RUN.md",
    DOCS / "BIBER_AZURE_DEVOPS_PRIVATE_PUBLISH.md",
]
REQUIRED_VSIX_MEMBERS = [
    "extension.vsixmanifest",
    "extension.vsomanifest",
    "overview.md",
    "static/index.html",
    "static/main.js",
    "static/styles.css",
    "tasks/biber-ai-pr-review/v1/task.json",
    "tasks/biber-ai-pr-review/v1/biber-ai-pr-review.js",
    "images/icon.png",
    "tasks/biber-ai-pr-review/v1/icon.png",
]


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def newest_vsix() -> Path | None:
    candidates = [*EXTENSION_ROOT.glob("*.vsix"), *(EXTENSION_ROOT / "dist").glob("*.vsix")]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


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


def pptx_slide_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            body = archive.read("ppt/presentation.xml")
    except (KeyError, zipfile.BadZipFile):
        return None
    root = ET.fromstring(body)
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    return len(root.findall(".//p:sldIdLst/p:sldId", ns))


def pptx_notes_count(path: Path) -> int:
    members = zip_members(path)
    return sum(1 for member in members if member.startswith("ppt/notesSlides/notesSlide"))


def text_bundle(paths: list[Path]) -> str:
    return "\n".join(read_text(path) for path in paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON artifact path.")
    args = parser.parse_args()

    vsix = newest_vsix()
    vsix_members = zip_members(vsix)
    talk = read_text(DOCS / "BIBER_AZURE_DEVOPS_CONFERENCE_TALK.md")
    runbook = read_text(DOCS / "BIBER_AZURE_DEVOPS_DEMO_RUNBOOK.md")
    handoff = read_text(DOCS / "CODEX_HANDOFF.md")
    package_json = read_text(EXTENSION_ROOT / "package.json")
    docs_text = text_bundle(REQUIRED_DOCS + [DOCS / "CODEX_HANDOFF.md"])
    extension_text = text_bundle(
        [
            EXTENSION_ROOT / "README.md",
            EXTENSION_ROOT / "overview.md",
            EXTENSION_ROOT / "vss-extension.json",
            EXTENSION_ROOT / "static" / "index.html",
            EXTENSION_ROOT / "static" / "main.js",
            EXTENSION_ROOT / "static" / "styles.css",
            EXTENSION_ROOT / "tasks" / "biber-ai-pr-review" / "v1" / "task.json",
            EXTENSION_ROOT / "tasks" / "biber-ai-pr-review" / "v1" / "biber-ai-pr-review.js",
        ]
    )
    all_text = docs_text + "\n" + extension_text

    checks: list[dict[str, Any]] = []
    checks.extend(check(path.is_file(), f"doc_exists:{path.name}") for path in REQUIRED_DOCS)
    checks.append(check(PPTX.is_file(), "pptx_exists"))
    checks.append(check(PPTX.stat().st_size > 80_000 if PPTX.is_file() else False, "pptx_nontrivial_size"))
    checks.append(check(pptx_slide_count(PPTX) == 16, "pptx_slide_count_16"))
    checks.append(check(pptx_notes_count(PPTX) >= 12, "pptx_speaker_notes_present"))
    checks.append(check("docs/BIBER_Azure_DevOps_Private_Code_Review_Talk.pptx" in talk, "talk_points_to_pptx"))
    checks.append(check("2026-08-31 BIBER Azure DevOps Conference Deck" in handoff, "handoff_records_deck"))
    checks.append(check("dry-run" in runbook.lower(), "runbook_keeps_dry_run_story"))
    checks.append(check("commentMode=post" in runbook, "runbook_mentions_explicit_post_mode"))
    checks.append(check('"validate:conference"' in package_json, "package_has_conference_smoke"))

    checks.append(check(vsix is not None and vsix.is_file(), "vsix_exists"))
    checks.append(check(vsix.stat().st_size > 100_000 if vsix else False, "vsix_nontrivial_size"))
    checks.extend(
        check(has_member_ending(vsix_members, member), f"vsix_contains:{member}")
        for member in REQUIRED_VSIX_MEMBERS
    )
    checks.append(check(not any("node_modules/" in member for member in vsix_members), "vsix_excludes_node_modules"))
    checks.append(check("BIBER AI Review" in extension_text, "extension_mentions_biber_review"))
    checks.append(check("testConnectionButton" in extension_text, "panel_has_connection_button"))
    checks.append(check("/models" in extension_text, "panel_tests_models_endpoint"))
    checks.append(check("BIBER_API_KEY" in extension_text, "task_uses_api_key_env"))
    checks.append(check("BIBER_ADMIN_API_KEY" not in extension_text, "extension_no_admin_key_path"))
    checks.append(check("Review with OpenAI mentor" not in extension_text, "extension_no_mentor_trigger"))
    checks.append(check("BIBER_TRAIN_APPROVED" not in extension_text, "extension_no_training_gate"))
    checks.append(check(not re.search(r"OPENAI_API_KEY\s*=\s*['\"][^'\"]{12,}", all_text), "no_openai_key_literal"))
    checks.append(check(not re.search(r"BIBER_ADMIN_API_KEY\s*=\s*['\"][^'\"]{12,}", all_text), "no_admin_key_literal"))
    checks.append(check(not re.search(r"BIBER_API_KEY\s*=\s*['\"][^'\"]{12,}", all_text), "no_biber_key_literal"))

    failed = [item for item in checks if not item["ok"]]
    result = {
        "source": "biber_azure_devops_conference_pack_smoke",
        "ok": not failed,
        "status": "passed" if not failed else "failed",
        "api_required": False,
        "azure_devops_request_sent": False,
        "external_network_required": False,
        "github_request_sent": False,
        "gpu_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "pptx": str(PPTX),
        "pptx_slide_count": pptx_slide_count(PPTX),
        "pptx_notes_count": pptx_notes_count(PPTX),
        "vsix": str(vsix) if vsix else None,
        "checks": checks,
        "failed": failed,
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

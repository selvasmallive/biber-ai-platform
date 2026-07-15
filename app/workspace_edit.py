from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.config import Settings
from app.repo_context import DENIED_NAMES, DENIED_PARTS, DENIED_SUFFIXES


class WorkspaceEditConfigurationError(RuntimeError):
    pass


class WorkspaceEditError(ValueError):
    pass


DENIED_EDIT_SUFFIXES = DENIED_SUFFIXES | {
    ".7z",
    ".bin",
    ".class",
    ".db",
    ".dll",
    ".dylib",
    ".exe",
    ".gif",
    ".gz",
    ".jar",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".so",
    ".tar",
    ".webp",
    ".zip",
}


def apply_workspace_edit(
    *,
    path: str,
    old_text: str | None,
    new_text: str,
    expected_replacements: int,
    create_if_missing: bool,
    dry_run: bool,
    settings: Settings,
) -> dict[str, Any]:
    root_path = _repo_root(settings)
    candidate = _resolve_edit_path(path, root_path)
    new_text_bytes = new_text.encode("utf-8")
    if len(new_text_bytes) > settings.workspace_edit_max_new_text_bytes:
        raise WorkspaceEditError(
            "Workspace edit new_text exceeds "
            f"{settings.workspace_edit_max_new_text_bytes} bytes."
        )

    if candidate.exists():
        return _replace_existing_file(
            candidate,
            root_path=root_path,
            old_text=old_text,
            new_text=new_text,
            expected_replacements=expected_replacements,
            dry_run=dry_run,
            settings=settings,
        )

    if not create_if_missing:
        raise WorkspaceEditError(f"Workspace edit target does not exist: {path}")
    if old_text not in (None, ""):
        raise WorkspaceEditError("old_text must be empty when creating a new file.")
    if len(new_text_bytes) > settings.workspace_edit_max_file_bytes:
        raise WorkspaceEditError(
            "Workspace edit output would exceed "
            f"{settings.workspace_edit_max_file_bytes} bytes."
        )

    if not dry_run:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_bytes(new_text_bytes)
    return _result(
        candidate,
        root_path=root_path,
        created=True,
        dry_run=dry_run,
        changed=True,
        replacements=0,
        old_bytes=b"",
        new_bytes=new_text_bytes,
    )


def plan_workspace_edits(
    *,
    edits: list[dict[str, Any]],
    settings: Settings,
    max_files: int = 8,
) -> dict[str, Any]:
    if max_files < 1:
        raise WorkspaceEditError("Workspace edit plan max_files must be at least 1.")
    if not edits:
        raise WorkspaceEditError("Workspace edit plan must include at least one edit.")
    if len(edits) > max_files:
        raise WorkspaceEditError(
            f"Workspace edit plan supports at most {max_files} file edits."
        )

    root_path = _repo_root(settings)
    planned: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    for index, edit in enumerate(edits):
        raw_path = str(edit.get("path") or "")
        try:
            candidate = _resolve_edit_path(raw_path, root_path)
            relative = candidate.relative_to(root_path).as_posix()
            if relative.lower() in seen_paths:
                raise WorkspaceEditError(
                    f"Workspace edit plan has duplicate target: {relative}"
                )
            seen_paths.add(relative.lower())

            result = apply_workspace_edit(
                path=relative,
                old_text=edit.get("old_text"),
                new_text=str(edit.get("new_text") or ""),
                expected_replacements=int(edit.get("expected_replacements") or 1),
                create_if_missing=bool(edit.get("create_if_missing")),
                dry_run=True,
                settings=settings,
            )
        except (TypeError, ValueError, WorkspaceEditError) as exc:
            rejected.append(
                {
                    "path": raw_path or f"<edit {index + 1}>",
                    "error": str(exc),
                }
            )
            continue

        operation = "create" if result["created"] else "replace"
        notes = _plan_notes(result)
        planned.append(
            {
                "path": result["path"],
                "operation": operation,
                "changed": result["changed"],
                "replacements": result["replacements"],
                "old_sha256": result["old_sha256"],
                "new_sha256": result["new_sha256"],
                "old_bytes": result["old_bytes"],
                "new_bytes": result["new_bytes"],
                "risk_level": _plan_risk_level(result),
                "notes": notes,
            }
        )

    total_new_bytes = sum(int(item["new_bytes"]) for item in planned)
    ok = bool(planned) and not rejected
    plan = {
        "ok": ok,
        "planned": planned,
        "rejected": rejected,
        "files_touched": len(planned),
        "total_new_bytes": total_new_bytes,
        "summary": (
            f"Planned {len(planned)} edit(s), rejected {len(rejected)} edit(s), "
            f"total output size {total_new_bytes} bytes."
        ),
    }
    plan["plan_hash"] = workspace_edit_plan_hash(plan)
    plan["review"] = review_workspace_edit_plan(plan)
    return plan


def review_workspace_edit_plan(plan: dict[str, Any]) -> dict[str, Any]:
    planned = [
        item for item in plan.get("planned", []) if isinstance(item, dict)
    ]
    rejected = [
        item for item in plan.get("rejected", []) if isinstance(item, dict)
    ]
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    operation_counts = {"replace": 0, "create": 0}
    warnings: list[str] = []
    hard_blockers: list[str] = []

    for item in planned:
        risk = str(item.get("risk_level") or "unknown")
        if risk not in risk_counts:
            risk_counts[risk] = 0
        risk_counts[risk] += 1
        operation = str(item.get("operation") or "unknown")
        if operation not in operation_counts:
            operation_counts[operation] = 0
        operation_counts[operation] += 1
        if operation == "create":
            warnings.append(f"creates_new_file:{item.get('path', '-')}")
        if int(item.get("replacements") or 0) > 1:
            warnings.append(f"multiple_replacements:{item.get('path', '-')}")
        if item.get("changed") is False:
            warnings.append(f"no_content_change:{item.get('path', '-')}")

    if not planned:
        hard_blockers.append("no_planned_edits")
    if rejected:
        hard_blockers.append("rejected_edits_present")

    ready_for_apply = bool(plan.get("ok")) and not hard_blockers
    return {
        "source": "biber_workspace_edit_plan_review",
        "ok": ready_for_apply,
        "review_status": (
            "ready_for_hash_guarded_apply" if ready_for_apply else "blocked"
        ),
        "ready_for_apply": ready_for_apply,
        "plan_hash": plan.get("plan_hash"),
        "planned_count": len(planned),
        "rejected_count": len(rejected),
        "files_touched": int(plan.get("files_touched") or 0),
        "total_new_bytes": int(plan.get("total_new_bytes") or 0),
        "risk_counts": risk_counts,
        "operation_counts": operation_counts,
        "warnings": list(dict.fromkeys(warnings)),
        "hard_blockers": hard_blockers,
        "required_actions": (
            ["apply_with_matching_plan_hash"]
            if ready_for_apply
            else ["fix_rejected_or_empty_edit_plan"]
        ),
        "affected_paths": [
            str(item.get("path"))
            for item in planned
            if isinstance(item.get("path"), str)
        ],
    }


def apply_workspace_edit_plan(
    *,
    edits: list[dict[str, Any]],
    expected_plan_hash: str,
    settings: Settings,
    max_files: int = 8,
) -> dict[str, Any]:
    normalized_expected_hash = expected_plan_hash.strip().lower()
    if not normalized_expected_hash:
        raise WorkspaceEditError("Workspace edit apply requires plan_hash.")

    plan = plan_workspace_edits(edits=edits, settings=settings, max_files=max_files)
    actual_hash = str(plan["plan_hash"])
    if actual_hash != normalized_expected_hash:
        raise WorkspaceEditError(
            "Workspace edit plan hash mismatch; re-run /v1/files/edit/plan "
            "against the current workspace state."
        )
    if not plan["ok"]:
        raise WorkspaceEditError("Workspace edit apply requires a clean edit plan.")

    root_path = _repo_root(settings)
    snapshots = _capture_apply_snapshots(plan["planned"], root_path)
    applied: list[dict[str, Any]] = []
    try:
        for edit in edits:
            result = apply_workspace_edit(
                path=str(edit.get("path") or ""),
                old_text=edit.get("old_text"),
                new_text=str(edit.get("new_text") or ""),
                expected_replacements=int(edit.get("expected_replacements") or 1),
                create_if_missing=bool(edit.get("create_if_missing")),
                dry_run=False,
                settings=settings,
            )
            applied.append(result)
    except (OSError, WorkspaceEditError, TypeError, ValueError) as exc:
        _restore_apply_snapshots(snapshots)
        raise WorkspaceEditError(
            f"Workspace edit apply failed and was rolled back: {exc}"
        ) from exc

    return {
        "ok": True,
        "plan_hash": actual_hash,
        "applied": applied,
        "files_touched": len(applied),
        "summary": f"Applied {len(applied)} workspace edit(s).",
    }


def workspace_edit_plan_hash(plan: dict[str, Any]) -> str:
    payload = {
        "planned": [
            {
                "path": item["path"],
                "operation": item["operation"],
                "changed": item["changed"],
                "replacements": item["replacements"],
                "old_sha256": item["old_sha256"],
                "new_sha256": item["new_sha256"],
                "old_bytes": item["old_bytes"],
                "new_bytes": item["new_bytes"],
                "risk_level": item["risk_level"],
            }
            for item in plan.get("planned", [])
        ],
        "rejected": plan.get("rejected", []),
        "files_touched": plan.get("files_touched", 0),
        "total_new_bytes": plan.get("total_new_bytes", 0),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _capture_apply_snapshots(
    planned: list[dict[str, Any]],
    root_path: Path,
) -> list[tuple[Path, bool, bytes]]:
    snapshots: list[tuple[Path, bool, bytes]] = []
    for item in planned:
        candidate = _resolve_edit_path(str(item["path"]), root_path)
        existed = candidate.exists()
        operation = str(item.get("operation") or "")
        if operation == "create" and existed:
            raise WorkspaceEditError(
                "Workspace edit target changed after planning; re-run the edit plan."
            )
        if operation != "create" and not existed:
            raise WorkspaceEditError(
                "Workspace edit target changed after planning; re-run the edit plan."
            )
        data = candidate.read_bytes() if existed else b""
        actual_old_sha = sha256(data).hexdigest() if data else None
        if actual_old_sha != item["old_sha256"]:
            raise WorkspaceEditError(
                "Workspace edit target changed after planning; re-run the edit plan."
            )
        snapshots.append((candidate, existed, data))
    return snapshots


def _restore_apply_snapshots(snapshots: list[tuple[Path, bool, bytes]]) -> None:
    rollback_errors: list[str] = []
    for candidate, existed, data in reversed(snapshots):
        try:
            if existed:
                candidate.write_bytes(data)
            elif candidate.exists():
                candidate.unlink()
        except OSError as exc:
            rollback_errors.append(f"{candidate.name}: {exc}")
    if rollback_errors:
        raise WorkspaceEditError(
            "Workspace edit rollback failed for: " + "; ".join(rollback_errors)
        )


def _replace_existing_file(
    candidate: Path,
    *,
    root_path: Path,
    old_text: str | None,
    new_text: str,
    expected_replacements: int,
    dry_run: bool,
    settings: Settings,
) -> dict[str, Any]:
    if not candidate.is_file():
        raise WorkspaceEditError(f"Workspace edit target is not a file: {candidate.name}")
    file_size = candidate.stat().st_size
    if file_size > settings.workspace_edit_max_file_bytes:
        raise WorkspaceEditError(
            "Workspace edit target exceeds "
            f"{settings.workspace_edit_max_file_bytes} bytes."
        )
    if not old_text:
        raise WorkspaceEditError("old_text is required when editing an existing file.")

    old_bytes = candidate.read_bytes()
    if b"\x00" in old_bytes:
        raise WorkspaceEditError(f"Workspace edit target appears to be binary: {candidate.name}")
    current = old_bytes.decode("utf-8", errors="replace")
    replacements = current.count(old_text)
    if replacements != expected_replacements:
        raise WorkspaceEditError(
            "Workspace edit replacement count mismatch: "
            f"expected {expected_replacements}, found {replacements}."
        )

    updated = current.replace(old_text, new_text, expected_replacements)
    updated_bytes = updated.encode("utf-8")
    if len(updated_bytes) > settings.workspace_edit_max_file_bytes:
        raise WorkspaceEditError(
            "Workspace edit output would exceed "
            f"{settings.workspace_edit_max_file_bytes} bytes."
        )
    changed = updated != current
    if changed and not dry_run:
        candidate.write_bytes(updated_bytes)

    return _result(
        candidate,
        root_path=root_path,
        created=False,
        dry_run=dry_run,
        changed=changed,
        replacements=replacements,
        old_bytes=old_bytes,
        new_bytes=updated_bytes,
    )


def _plan_notes(result: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if result["created"]:
        notes.append("creates a new file")
    if not result["changed"]:
        notes.append("does not change file content")
    if int(result["replacements"]) > 1:
        notes.append("replaces multiple occurrences")
    return notes


def _plan_risk_level(result: dict[str, Any]) -> str:
    if result["created"] or int(result["replacements"]) > 1:
        return "medium"
    if not result["changed"]:
        return "low"
    return "low"


def _repo_root(settings: Settings) -> Path:
    root_path = Path(settings.repo_context_root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise WorkspaceEditConfigurationError(
            f"Workspace edit root is not a directory: {root_path}"
        )
    return root_path


def _resolve_edit_path(raw_path: str, root_path: Path) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise WorkspaceEditError("Workspace edit path is empty or invalid.")

    requested = Path(raw_path)
    if requested.is_absolute() or requested.drive or _has_windows_drive_prefix(raw_path):
        raise WorkspaceEditError(f"Workspace edit path must be workspace-relative: {raw_path}")
    if _is_denied_edit_path(requested):
        raise WorkspaceEditError(f"Workspace edit path is not allowed: {raw_path}")

    candidate = (root_path / requested).resolve()
    try:
        relative = candidate.relative_to(root_path)
    except ValueError as exc:
        raise WorkspaceEditError(f"Workspace edit path escapes the workspace: {raw_path}") from exc
    if _is_denied_edit_path(relative):
        raise WorkspaceEditError(f"Workspace edit path is not allowed: {raw_path}")
    return candidate


def _is_denied_edit_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return (
        bool(parts.intersection(DENIED_PARTS))
        or name in DENIED_NAMES
        or any(name.endswith(suffix) for suffix in DENIED_EDIT_SUFFIXES)
    )


def _has_windows_drive_prefix(raw_path: str) -> bool:
    return len(raw_path) >= 2 and raw_path[0].isalpha() and raw_path[1] == ":"


def _result(
    candidate: Path,
    *,
    root_path: Path,
    created: bool,
    dry_run: bool,
    changed: bool,
    replacements: int,
    old_bytes: bytes,
    new_bytes: bytes,
) -> dict[str, Any]:
    return {
        "path": candidate.relative_to(root_path).as_posix(),
        "created": created,
        "dry_run": dry_run,
        "changed": changed,
        "replacements": replacements,
        "old_sha256": sha256(old_bytes).hexdigest() if old_bytes else None,
        "new_sha256": sha256(new_bytes).hexdigest(),
        "old_bytes": len(old_bytes),
        "new_bytes": len(new_bytes),
    }

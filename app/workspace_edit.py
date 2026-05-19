from __future__ import annotations

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
    return {
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
    if requested.is_absolute() or requested.drive:
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

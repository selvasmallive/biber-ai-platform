from __future__ import annotations

from pathlib import Path


class RepoContextError(ValueError):
    pass


DENIED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
}
DENIED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_ed25519",
}
DENIED_SUFFIXES = {".key", ".pem", ".pfx", ".p12"}


def build_repo_context_message(
    paths: list[str] | tuple[str, ...] | None,
    *,
    root: str,
    max_files: int,
    max_bytes_per_file: int,
    max_total_bytes: int,
) -> str | None:
    if not paths:
        return None
    if len(paths) > max_files:
        raise RepoContextError(f"Too many repo context files requested; max is {max_files}.")

    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise RepoContextError(f"Repo context root is not a directory: {root_path}")

    sections: list[str] = []
    total_bytes = 0
    seen: set[Path] = set()
    for raw_path in paths:
        candidate = _resolve_requested_path(raw_path, root_path)
        if candidate in seen:
            continue
        seen.add(candidate)

        if total_bytes >= max_total_bytes:
            break
        remaining = max_total_bytes - total_bytes
        section, bytes_used = _read_context_file(
            candidate,
            root_path=root_path,
            max_bytes=min(max_bytes_per_file, remaining),
        )
        sections.append(section)
        total_bytes += bytes_used

    if not sections:
        return None

    return "\n\n".join(
        [
            (
                "Repository context from selected files. Treat this as read-only context; "
                "do not assume files not shown here."
            ),
            *sections,
        ]
    )


def _resolve_requested_path(raw_path: str, root_path: Path) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise RepoContextError("Repo context path is empty or invalid.")

    requested = Path(raw_path)
    if requested.is_absolute():
        raise RepoContextError(f"Repo context path must be workspace-relative: {raw_path}")
    if _is_denied_path(requested):
        raise RepoContextError(f"Repo context path is not allowed: {raw_path}")

    candidate = (root_path / requested).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise RepoContextError(f"Repo context path escapes the workspace: {raw_path}") from exc

    if _is_denied_path(candidate.relative_to(root_path)):
        raise RepoContextError(f"Repo context path is not allowed: {raw_path}")
    if not candidate.exists() or not candidate.is_file():
        raise RepoContextError(f"Repo context file does not exist: {raw_path}")
    return candidate


def _is_denied_path(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return (
        bool(parts.intersection(DENIED_PARTS))
        or name in DENIED_NAMES
        or any(name.endswith(suffix) for suffix in DENIED_SUFFIXES)
    )


def _read_context_file(candidate: Path, *, root_path: Path, max_bytes: int) -> tuple[str, int]:
    if max_bytes <= 0:
        raise RepoContextError("Repo context byte budget is exhausted.")

    file_size = candidate.stat().st_size
    read_size = min(file_size, max_bytes)
    with candidate.open("rb") as handle:
        data = handle.read(read_size)
    if b"\x00" in data:
        raise RepoContextError(f"Repo context file appears to be binary: {candidate.name}")

    text = data.decode("utf-8", errors="replace")
    relative = candidate.relative_to(root_path).as_posix()
    truncated = file_size > read_size
    marker = " truncated" if truncated else ""
    header = f"--- FILE: {relative} ({file_size} bytes{marker}) ---"
    return f"{header}\n{text}", len(data)

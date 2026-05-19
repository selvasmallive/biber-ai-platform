from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


class RepoContextError(ValueError):
    pass


DENIED_PARTS = {
    ".next",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "bin",
    "build",
    "coverage",
    "dist",
    "venv",
    "node_modules",
    "obj",
    "target",
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
IGNORED_SUFFIXES = {
    ".7z",
    ".bin",
    ".bmp",
    ".class",
    ".dll",
    ".exe",
    ".gif",
    ".ico",
    ".jar",
    ".jpg",
    ".jpeg",
    ".lockb",
    ".mp3",
    ".mp4",
    ".o",
    ".obj",
    ".pdf",
    ".png",
    ".so",
    ".wasm",
    ".webp",
    ".zip",
}
SOURCE_SUFFIXES = {
    ".cs",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".xml",
    ".yaml",
    ".yml",
}
MANIFEST_NAMES = {
    "build.gradle",
    "build.gradle.kts",
    "cargo.lock",
    "cargo.toml",
    "directory.build.props",
    "directory.packages.props",
    "global.json",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "settings.gradle",
    "settings.gradle.kts",
    "setup.py",
    "tsconfig.json",
}


@dataclass(frozen=True)
class _ContextCandidate:
    path: str
    reason: str
    priority: int
    project_type: str | None = None


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


def plan_repo_context(
    *,
    root: str,
    instruction: str | None = None,
    pinned_paths: list[str] | tuple[str, ...] | None = None,
    changed_paths: list[str] | tuple[str, ...] | None = None,
    max_files: int = 12,
    max_scan_files: int = 2000,
) -> dict[str, object]:
    if max_files < 1:
        raise RepoContextError("Repo context plan max_files must be at least 1.")

    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise RepoContextError(f"Repo context root is not a directory: {root_path}")

    scanned_files = list(_iter_repo_files(root_path, max_scan_files=max_scan_files))
    detected_project_types = sorted(
        {
            project_type
            for relative in scanned_files
            if (project_type := _project_type_for_path(relative)) is not None
        }
    )

    candidates: list[_ContextCandidate] = []
    skipped: list[dict[str, str]] = []

    def add_candidate(
        relative: Path,
        *,
        reason: str,
        priority: int,
        project_type: str | None = None,
    ) -> None:
        if not _is_plan_candidate_file(relative):
            skipped.append(
                {
                    "path": relative.as_posix(),
                    "reason": "not a text source, manifest, or documentation file",
                }
            )
            return
        candidates.append(
            _ContextCandidate(
                path=relative.as_posix(),
                reason=reason,
                priority=priority,
                project_type=project_type or _project_type_for_path(relative),
            )
        )

    for raw_path in pinned_paths or ():
        candidate = _resolve_requested_path(raw_path, root_path)
        add_candidate(
            candidate.relative_to(root_path),
            reason="pinned",
            priority=0,
        )

    for raw_path in changed_paths or ():
        try:
            candidate = _resolve_requested_path(raw_path, root_path)
        except RepoContextError as exc:
            skipped.append({"path": raw_path, "reason": str(exc)})
            continue
        relative = candidate.relative_to(root_path)
        add_candidate(
            relative,
            reason="changed",
            priority=10,
            project_type=_project_type_for_source(relative),
        )
        for related in _related_test_paths(relative, scanned_files):
            add_candidate(
                related,
                reason=f"related test for {relative.as_posix()}",
                priority=20,
                project_type=_project_type_for_source(related),
            )

    for relative in scanned_files:
        if _is_manifest_file(relative):
            add_candidate(
                relative,
                reason="project manifest",
                priority=30,
            )

    for relative in scanned_files:
        if relative.name.lower().startswith("readme"):
            add_candidate(relative, reason="repository overview", priority=40)

    for relative in _instruction_matched_files(instruction or "", scanned_files):
        add_candidate(
            relative,
            reason="matched instruction terms",
            priority=50,
            project_type=_project_type_for_source(relative),
        )

    selected = _dedupe_and_select(candidates, max_files=max_files)
    selected_paths = [candidate.path for candidate in selected]
    summary = (
        f"Detected {', '.join(detected_project_types) or 'unknown'} project type(s); "
        f"selected {len(selected_paths)} context file(s)."
    )

    return {
        "selected_paths": selected_paths,
        "detected_project_types": detected_project_types,
        "candidates": [
            {
                "path": candidate.path,
                "reason": candidate.reason,
                "project_type": candidate.project_type,
                "priority": candidate.priority,
            }
            for candidate in selected
        ],
        "skipped": skipped,
        "summary": summary,
    }


def _iter_repo_files(root_path: Path, *, max_scan_files: int) -> list[Path]:
    results: list[Path] = []
    stack = [root_path]
    while stack and len(results) < max_scan_files:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda path: path.name.lower())
        except OSError:
            continue
        for child in children:
            try:
                relative = child.relative_to(root_path)
            except ValueError:
                continue
            if _is_denied_path(relative):
                continue
            if child.is_dir():
                stack.append(child)
            elif child.is_file():
                results.append(relative)
                if len(results) >= max_scan_files:
                    break
    return results


def _project_type_for_path(path: Path) -> str | None:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name.endswith(".csproj") or suffix == ".sln" or name in {
        "directory.build.props",
        "directory.packages.props",
        "global.json",
    }:
        return "dotnet"
    if name in {"pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"}:
        return "java"
    if name in {"settings.gradle.kts"}:
        return "java"
    if name in {"cargo.toml", "cargo.lock"}:
        return "rust"
    if name in {"package.json", "tsconfig.json"} or name.startswith(
        ("vite.config", "next.config")
    ):
        return "node-react"
    if name in {"pyproject.toml", "requirements.txt", "setup.py"}:
        return "python"
    return _project_type_for_source(path)


def _project_type_for_source(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".cs":
        return "dotnet"
    if suffix in {".java", ".kt"}:
        return "java"
    if suffix == ".rs":
        return "rust"
    if suffix in {".js", ".jsx", ".ts", ".tsx", ".css", ".html"}:
        return "node-react"
    if suffix == ".py":
        return "python"
    return None


def _is_manifest_file(path: Path) -> bool:
    name = path.name.lower()
    return name in MANIFEST_NAMES or name.endswith(".csproj") or name.endswith(".sln")


def _is_plan_candidate_file(path: Path) -> bool:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if _is_denied_path(path) or suffix in IGNORED_SUFFIXES:
        return False
    return _is_manifest_file(path) or suffix in SOURCE_SUFFIXES or name.startswith("readme")


def _related_test_paths(changed: Path, scanned_files: list[Path]) -> list[Path]:
    changed_stem = changed.stem.lower()
    suffix = changed.suffix.lower()
    if not changed_stem or not suffix:
        return []

    related: list[Path] = []
    for relative in scanned_files:
        if relative == changed or relative.suffix.lower() != suffix:
            continue
        path_text = relative.as_posix().lower()
        stem = relative.stem.lower()
        if not _looks_like_test_path(relative):
            continue
        if changed_stem in stem or stem in {
            f"test_{changed_stem}",
            f"{changed_stem}_test",
            f"{changed_stem}_tests",
            f"{changed_stem}test",
            f"{changed_stem}tests",
        }:
            related.append(relative)
        elif changed_stem in path_text:
            related.append(relative)
    return sorted(related, key=lambda path: path.as_posix())[:4]


def _looks_like_test_path(path: Path) -> bool:
    path_text = path.as_posix().lower()
    stem = path.stem.lower()
    return (
        "/test/" in path_text
        or "/tests/" in path_text
        or ".tests/" in path_text
        or stem.startswith("test_")
        or stem.endswith("_test")
        or stem.endswith("_tests")
        or stem.endswith("test")
        or stem.endswith("tests")
    )


def _instruction_matched_files(instruction: str, scanned_files: list[Path]) -> list[Path]:
    tokens = {
        token
        for token in re.findall(r"[a-zA-Z0-9_]{3,}", instruction.lower())
        if token not in {"the", "and", "for", "with", "this", "that", "from"}
    }
    if not tokens:
        return []

    matches: list[Path] = []
    for relative in scanned_files:
        if not _is_plan_candidate_file(relative):
            continue
        path_text = relative.as_posix().lower()
        if any(token in path_text for token in tokens):
            matches.append(relative)
    return sorted(matches, key=lambda path: path.as_posix())[:12]


def _dedupe_and_select(
    candidates: list[_ContextCandidate],
    *,
    max_files: int,
) -> list[_ContextCandidate]:
    selected: list[_ContextCandidate] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: (item.priority, item.path)):
        key = candidate.path.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(candidate)
        if len(selected) >= max_files:
            break
    return selected

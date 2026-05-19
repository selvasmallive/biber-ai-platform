from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DENIED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".mypy_cache",
}
DENIED_FILE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "id_rsa",
    "id_ed25519",
}
DENIED_SUFFIXES = {
    ".key",
    ".pem",
    ".pfx",
    ".p12",
    ".sqlite",
    ".db",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".exe",
    ".dll",
}
LANGUAGE_BY_SUFFIX = {
    ".rs": "Rust",
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".js": "JavaScript",
    ".jsx": "JavaScript React",
    ".css": "CSS",
    ".html": "HTML",
    ".sql": "SQL",
    ".md": "Markdown",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".sh": "Bash",
    ".ps1": "PowerShell",
    ".cs": "C#",
    ".java": "Java",
    ".kt": "Kotlin",
    ".go": "Go",
}
ROLE_HINTS = (
    ("test", "test"),
    ("tests", "test"),
    ("spec", "test"),
    ("docs", "documentation"),
    ("readme", "documentation"),
    ("migrations", "database"),
    ("schema", "database"),
    ("docker", "devops"),
    ("kubernetes", "devops"),
    ("deploy", "devops"),
    ("security", "security"),
    ("crypto", "cryptography"),
    ("wallet", "wallet"),
    ("ledger", "ledger"),
    ("mempool", "mempool"),
    ("consensus", "consensus"),
)
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^'\"\s]{12,}"),
)


@dataclass(frozen=True)
class RepoFileSummary:
    path: str
    bytes: int
    sha256: str
    language: str
    role: str


def safe_relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_denied_path(path: Path, root: Path) -> str | None:
    rel_parts = tuple(part.lower() for part in path.relative_to(root).parts)
    if any(part in DENIED_DIR_NAMES for part in rel_parts[:-1]):
        return "denied_directory"
    name = rel_parts[-1]
    if name in DENIED_FILE_NAMES:
        return "denied_filename"
    if any(name.endswith(suffix) for suffix in DENIED_SUFFIXES):
        return "denied_suffix"
    if "secret" in name or "credential" in name:
        return "secret_like_filename"
    return None


def language_for(path: Path) -> str:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "Other")


def role_for(path: Path) -> str:
    lower_path = path.as_posix().lower()
    for needle, role in ROLE_HINTS:
        if needle in lower_path:
            return role
    return "implementation"


def has_possible_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def scan_repo(
    repo_root: Path,
    *,
    max_files: int = 200,
    max_file_bytes: int = 200_000,
) -> tuple[list[RepoFileSummary], Counter[str], int]:
    root = repo_root.resolve()
    summaries: list[RepoFileSummary] = []
    skipped: Counter[str] = Counter()
    scanned = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        scanned += 1
        denied_reason = is_denied_path(path, root)
        if denied_reason:
            skipped[denied_reason] += 1
            continue
        if language_for(path) == "Other":
            skipped["unsupported_extension"] += 1
            continue
        size = path.stat().st_size
        if size > max_file_bytes:
            skipped["too_large"] += 1
            continue
        try:
            data = path.read_bytes()
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            skipped["non_utf8"] += 1
            continue
        if has_possible_secret(text):
            skipped["possible_secret"] += 1
            continue
        relative_path = safe_relative_path(path, root)
        summaries.append(
            RepoFileSummary(
                path=relative_path,
                bytes=size,
                sha256=hashlib.sha256(data).hexdigest(),
                language=language_for(path),
                role=role_for(Path(relative_path)),
            )
        )
        if len(summaries) >= max_files:
            skipped["max_files_reached"] += 1
            break
    return summaries, skipped, scanned


def build_eval_prompts(files: list[RepoFileSummary], *, max_prompts: int = 12) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for file in files:
        key = (file.language, file.role)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        prompt_id = re.sub(r"[^a-z0-9]+", "-", f"repo-{file.language}-{file.role}".lower())
        prompt_id = prompt_id.strip("-") or "repo-adaptation"
        prompts.append(
            {
                "id": prompt_id,
                "prompt": (
                    "Using the repository conventions, explain the safest next "
                    f"implementation step for a {file.role} change related to "
                    f"`{file.path}`. Keep the answer specific and test-oriented."
                ),
                "language": file.language,
                "task_type": "repo_adaptation_eval",
                "temperature": 0.0,
                "max_tokens": 256,
                "expect_contains": [file.role],
            }
        )
        if len(prompts) >= max_prompts:
            break
    return prompts


def build_plan(
    repo_root: Path,
    *,
    max_files: int,
    max_file_bytes: int,
    max_prompts: int,
) -> dict[str, Any]:
    files, skipped, scanned = scan_repo(
        repo_root,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
    )
    languages = Counter(file.language for file in files)
    roles = Counter(file.role for file in files)
    eval_prompts = build_eval_prompts(files, max_prompts=max_prompts)
    return {
        "command": "biber-repo-adaptation-plan",
        "generated_at": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root.resolve()),
        "strategy": {
            "default": "repo_context_first",
            "fine_tune_only_after": [
                "repeated_model_failures",
                "curated_training_examples",
                "held_out_eval_prompts",
                "candidate_beats_current_model",
            ],
            "codex_role": "mentor_reviewer_only",
            "training_runtime": "vast_gpu",
        },
        "scanned_files": scanned,
        "included_files": len(files),
        "skipped": dict(skipped),
        "languages": dict(languages),
        "roles": dict(roles),
        "files": [asdict(file) for file in files],
        "suggested_eval_prompts": eval_prompts,
        "next_steps": [
            "Use repo_context_paths with the most relevant files before training.",
            "Run the suggested eval prompts against the current BIBER model.",
            "Collect failures and reviewed fixes as small JSONL training records.",
            "Train a candidate adapter on Vast only after eval gaps are repeatable.",
            "Promote a candidate only if it beats the current adapter on held-out evals.",
        ],
    }


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a safe BIBER repo-adaptation plan before fine-tuning."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--eval-prompts-output", type=Path)
    parser.add_argument("--max-files", type=int, default=200)
    parser.add_argument("--max-file-bytes", type=int, default=200_000)
    parser.add_argument("--max-prompts", type=int, default=12)
    args = parser.parse_args(argv)

    if not args.repo_root.exists() or not args.repo_root.is_dir():
        parser.error(f"--repo-root must be an existing directory: {args.repo_root}")
    plan = build_plan(
        args.repo_root,
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
        max_prompts=args.max_prompts,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.eval_prompts_output:
        write_jsonl(args.eval_prompts_output, plan["suggested_eval_prompts"])

    print(f"Repo adaptation plan: {args.output}")
    print(f"Included files: {plan['included_files']}")
    print(f"Suggested eval prompts: {len(plan['suggested_eval_prompts'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

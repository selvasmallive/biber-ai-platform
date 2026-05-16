from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ".env.example",
    "Dockerfile",
    "README.md",
    "app/__init__.py",
    "app/auth.py",
    "app/azure_backup.py",
    "app/config.py",
    "app/github_client.py",
    "app/llm.py",
    "app/main.py",
    "app/scheduler.py",
    "db/schema.sql",
    "docker-compose.yml",
    "docker-compose.gpu.yml",
    "docs/API_EXAMPLES.md",
    "docs/ARCHITECTURE.md",
    "docs/NEXT_STEPS_ON_GPU.md",
    "docs/PHASE1_GAP_ANALYSIS.md",
    "docs/VAST_DIRECT_DEPLOY.md",
    "docs/phase1-vast-deploy.md",
    "pyproject.toml",
    "requirements-api.txt",
    "requirements-worker.txt",
    "scripts/lib/vast_direct_common.sh",
    "scripts/vast_bootstrap_direct.sh",
    "scripts/vast_start_direct.sh",
    "scripts/vast_status_direct.sh",
    "scripts/vast_stop_direct.sh",
    "scripts/vast_test_direct.sh",
    "src/biber_api/__init__.py",
    "src/biber_api/azure_backup.py",
    "src/biber_api/config.py",
    "src/biber_api/github.py",
    "src/biber_api/llm.py",
    "src/biber_api/main.py",
    "src/biber_api/schemas.py",
    "src/biber_api/security.py",
    "worker/__init__.py",
    "worker/main.py",
]


def main() -> int:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        print("Missing required files:")
        for path in missing:
            print(f"  - {path}")
        return 1

    for py_file in sorted((ROOT / "src").rglob("*.py")):
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    for py_file in sorted((ROOT / "app").rglob("*.py")):
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    for py_file in sorted((ROOT / "worker").rglob("*.py")):
        ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))

    conflict_markers = []
    for path in sorted(ROOT.rglob("*")):
        if ".git" in path.parts or path.is_dir():
            continue
        if path.suffix.lower() in {".zip", ".png", ".jpg", ".jpeg", ".pdf", ".docx"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(
            line.startswith(("<<<<<<<", "=======", ">>>>>>>"))
            for line in text.splitlines()
        ):
            conflict_markers.append(path.relative_to(ROOT).as_posix())

    if conflict_markers:
        print("Merge conflict markers remain:")
        for path in conflict_markers:
            print(f"  - {path}")
        return 1

    print("Phase 1 scaffold validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

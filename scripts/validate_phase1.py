from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    ".env.example",
    "Dockerfile",
    "README.md",
    "docker-compose.gpu.yml",
    "docs/phase1-vast-deploy.md",
    "pyproject.toml",
    "src/biber_api/__init__.py",
    "src/biber_api/azure_backup.py",
    "src/biber_api/config.py",
    "src/biber_api/github.py",
    "src/biber_api/llm.py",
    "src/biber_api/main.py",
    "src/biber_api/schemas.py",
    "src/biber_api/security.py",
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

    print("Phase 1 scaffold validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

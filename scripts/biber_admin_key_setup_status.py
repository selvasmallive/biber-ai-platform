from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

try:
    from biber_admin_console_readiness import read_dotenv_value
except ModuleNotFoundError:
    from scripts.biber_admin_console_readiness import read_dotenv_value


SOURCE = "biber_admin_key_setup_status"
ADMIN_KEY_NAME = "BIBER_ADMIN_API_KEY"
STORE_PATH_NAME = "BIBER_API_KEY_STORE_PATH"
DEFAULT_VAST_STORE_PATH = "/workspace/outputs/biber-api-keys.json"


def detect_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_dotenv_path(value: str | None, repo_root: Path) -> Path:
    if value:
        path = Path(value)
        return path if path.is_absolute() else repo_root / path
    return repo_root / ".env"


def value_presence_from_env_or_dotenv(
    *,
    name: str,
    dotenv_path: Path,
) -> tuple[bool, str | None]:
    if os.getenv(name):
        return True, "environment"
    if read_dotenv_value(str(dotenv_path), name):
        return True, "dotenv_file"
    return False, None


def build_status(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else detect_repo_root()
    dotenv_path = resolve_dotenv_path(args.dotenv, repo_root)
    admin_key_configured, admin_key_source = value_presence_from_env_or_dotenv(
        name=ADMIN_KEY_NAME,
        dotenv_path=dotenv_path,
    )
    store_path = os.getenv(STORE_PATH_NAME) or read_dotenv_value(str(dotenv_path), STORE_PATH_NAME)
    if not store_path:
        store_path = DEFAULT_VAST_STORE_PATH if str(repo_root).startswith("/workspace") else ".biber-runtime/biber-api-keys.json"

    if admin_key_configured:
        recommended_next_step = "run_redacted_admin_console_list_flow_readiness"
        status = "admin_key_configured"
    else:
        recommended_next_step = "configure_admin_key_only_when_deliberately_needed"
        status = "admin_key_missing"

    return {
        "source": SOURCE,
        "ok": admin_key_configured or args.allow_missing,
        "status": status,
        "repo_root": str(repo_root),
        "dotenv_path": str(dotenv_path),
        "dotenv_exists": dotenv_path.exists(),
        "admin_api_key_env": ADMIN_KEY_NAME,
        "admin_api_key_configured": admin_key_configured,
        "admin_api_key_source": admin_key_source,
        "admin_api_key_included": False,
        "raw_key_records_included": False,
        "mutation_performed": False,
        "credential_rotation_performed": False,
        "api_key_store_path": store_path,
        "approval_required": "BIBER_CONFIGURE_ADMIN_API_KEY_APPROVED=1",
        "persist_admin_key_env": "BIBER_PERSIST_ADMIN_API_KEY=1",
        "fastapi_restart_scope": "FastAPI only; vLLM/model runtime should stay running",
        "recommended_next_step": recommended_next_step,
        "guarded_setup_command": [
            "cd /workspace/biber-ai-platform",
            'read -rsp "Paste BIBER_ADMIN_API_KEY: " BIBER_ADMIN_API_KEY',
            "echo",
            "export BIBER_ADMIN_API_KEY",
            "export BIBER_PERSIST_ADMIN_API_KEY=1",
            "export BIBER_CONFIGURE_ADMIN_API_KEY_APPROVED=1",
            "bash scripts/vast_configure_admin_api_key.sh",
            "unset BIBER_ADMIN_API_KEY",
        ],
        "post_setup_readiness_command": [
            "cd /workspace/biber-ai-platform",
            "/workspace/biber-venv/bin/python scripts/biber_admin_console_readiness.py",
            "  --base-url http://127.0.0.1:8000",
            "  --admin-api-key-env BIBER_ADMIN_API_KEY",
            "  --admin-api-key-dotenv .env",
            "  --require-console-served",
            "  --require-authenticated-admin-list",
            "  --require-admin-console-list-flow",
            "  --output /workspace/outputs/biber-admin-console-list-flow-local.json",
        ],
    }


def write_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report no-secret BIBER admin API-key setup status and guarded next steps."
    )
    parser.add_argument("--repo-root", help="Repository root. Defaults to this script's repo.")
    parser.add_argument("--dotenv", help="Optional dotenv path. Defaults to <repo-root>/.env.")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Return success even when BIBER_ADMIN_API_KEY is not configured.",
    )
    parser.add_argument("--output", help="Optional path for the redacted status artifact JSON.")
    args = parser.parse_args(argv)

    status = build_status(args)
    write_json(args.output, status)
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

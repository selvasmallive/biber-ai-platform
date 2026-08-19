from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.biber_admin_key_setup_status import build_status


def args_for(tmp_path: Path, *, allow_missing: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        repo_root=str(tmp_path),
        dotenv=str(tmp_path / ".env"),
        allow_missing=allow_missing,
        output=None,
    )


def test_admin_key_setup_status_missing_is_redacted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BIBER_ADMIN_API_KEY", raising=False)

    status = build_status(args_for(tmp_path, allow_missing=True))
    serialized = json.dumps(status)

    assert status["ok"] is True
    assert status["status"] == "admin_key_missing"
    assert status["admin_api_key_configured"] is False
    assert status["admin_api_key_included"] is False
    assert status["mutation_performed"] is False
    assert "Paste BIBER_ADMIN_API_KEY" in serialized


def test_admin_key_setup_status_dotenv_configured_omits_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BIBER_ADMIN_API_KEY", raising=False)
    secret_value = "admin-secret-value"
    (tmp_path / ".env").write_text(
        f"BIBER_ADMIN_API_KEY='{secret_value}'\n"
        "BIBER_API_KEY_STORE_PATH=/workspace/outputs/custom-api-keys.json\n",
        encoding="utf-8",
    )

    status = build_status(args_for(tmp_path))
    serialized = json.dumps(status)

    assert status["ok"] is True
    assert status["status"] == "admin_key_configured"
    assert status["admin_api_key_configured"] is True
    assert status["admin_api_key_source"] == "dotenv_file"
    assert status["api_key_store_path"] == "/workspace/outputs/custom-api-keys.json"
    assert secret_value not in serialized
    assert status["raw_key_records_included"] is False
    assert status["credential_rotation_performed"] is False


def test_admin_key_setup_status_env_takes_precedence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BIBER_ADMIN_API_KEY", "env-secret-value")
    (tmp_path / ".env").write_text("BIBER_ADMIN_API_KEY='dotenv-secret-value'\n", encoding="utf-8")

    status = build_status(args_for(tmp_path))
    serialized = json.dumps(status)

    assert status["admin_api_key_configured"] is True
    assert status["admin_api_key_source"] == "environment"
    assert "env-secret-value" not in serialized
    assert "dotenv-secret-value" not in serialized

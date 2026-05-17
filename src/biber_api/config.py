from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _priority_passcodes(value: str | None) -> dict[str, int]:
    passcodes: dict[str, int] = {}
    for item in _csv(value):
        passcode, _, priority = item.partition(":")
        if not passcode:
            continue
        try:
            passcodes[passcode] = int(priority or "0")
        except ValueError:
            passcodes[passcode] = 0
    return passcodes


@dataclass(frozen=True)
class BiberSettings:
    env: str
    api_keys: tuple[str, ...]
    priority_passcodes: dict[str, int]
    local_model_base_url: str
    local_model_name: str
    local_model_timeout_seconds: float
    mentor_enabled: bool
    openai_base_url: str
    openai_api_key: str | None
    openai_model: str | None
    github_token: str | None
    github_default_owner: str | None
    github_default_repo: str | None
    azure_storage_connection_string: str | None
    azure_blob_container: str
    default_model: str = "biber-dev-core-v1"
    repo_context_root: str = "."
    repo_context_max_files: int = 12
    repo_context_max_bytes_per_file: int = 12000
    repo_context_max_total_bytes: int = 40000


@lru_cache(maxsize=1)
def get_settings() -> BiberSettings:
    return BiberSettings(
        env=os.getenv("BIBER_ENV", "dev"),
        api_keys=_csv(os.getenv("BIBER_API_KEYS")),
        priority_passcodes=_priority_passcodes(os.getenv("BIBER_PRIORITY_PASSCODES")),
        local_model_base_url=os.getenv("BIBER_LOCAL_MODEL_BASE_URL", "http://localhost:8000/v1"),
        local_model_name=os.getenv("BIBER_LOCAL_MODEL_NAME", "biber-dev-core"),
        local_model_timeout_seconds=float(os.getenv("BIBER_LOCAL_MODEL_TIMEOUT_SECONDS", "180")),
        mentor_enabled=_bool(os.getenv("BIBER_MENTOR_ENABLED"), default=False),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL") or None,
        github_token=os.getenv("GITHUB_TOKEN") or None,
        github_default_owner=os.getenv("GITHUB_DEFAULT_OWNER") or None,
        github_default_repo=os.getenv("GITHUB_DEFAULT_REPO") or None,
        azure_storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING") or None,
        azure_blob_container=os.getenv("AZURE_BLOB_CONTAINER", "biber-backups"),
        default_model=os.getenv("BIBER_DEFAULT_MODEL", "biber-dev-core-v1"),
        repo_context_root=os.getenv("BIBER_REPO_CONTEXT_ROOT") or os.getcwd(),
        repo_context_max_files=int(os.getenv("BIBER_REPO_CONTEXT_MAX_FILES", "12")),
        repo_context_max_bytes_per_file=int(
            os.getenv("BIBER_REPO_CONTEXT_MAX_BYTES_PER_FILE", "12000")
        ),
        repo_context_max_total_bytes=int(os.getenv("BIBER_REPO_CONTEXT_MAX_TOTAL_BYTES", "40000")),
    )

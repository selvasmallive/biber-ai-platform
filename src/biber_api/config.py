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


def _default_agent_session_dir(repo_context_root: str) -> str:
    configured = os.getenv("BIBER_AGENT_SESSION_DIR")
    if configured:
        return configured
    if os.path.isdir("/workspace") and os.access("/workspace", os.W_OK):
        return "/workspace/outputs/agent-sessions"
    return os.path.join(repo_context_root, ".biber-runtime", "agent-sessions")


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
    runtime_profiles_enabled: bool = False
    repo_context_root: str = "."
    agent_session_dir: str = ""
    repo_context_max_files: int = 12
    repo_context_max_bytes_per_file: int = 12000
    repo_context_max_total_bytes: int = 40000
    xriq_workspace_dir: str = "xriq"
    xriq_node_command: str = "cargo run -q -p xriq-node --"
    xriq_chain_file: str = "target/biber-xriq-private-devnet-chain.bin"
    xriq_pending_file: str = "target/biber-xriq-private-devnet-pending.tsv"
    xriq_snapshot_root_dir: str = "target/biber-xriq-private-devnet-snapshots"
    xriq_snapshot_import_root_dir: str = "target/biber-xriq-private-devnet-imports"
    xriq_default_alice_balance_base_units: str = "100"
    xriq_command_timeout_seconds: float = 30.0
    xriq_rustup_home: str | None = None
    xriq_cargo_home: str | None = None
    xriq_path_prefix: str | None = None
    test_runner_timeout_seconds: float = 120.0
    test_runner_max_output_bytes: int = 12000
    workspace_edit_max_file_bytes: int = 200000
    workspace_edit_max_new_text_bytes: int = 120000


@lru_cache(maxsize=1)
def get_settings() -> BiberSettings:
    repo_context_root = os.getenv("BIBER_REPO_CONTEXT_ROOT") or os.getcwd()
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
        runtime_profiles_enabled=_bool(
            os.getenv("BIBER_RUNTIME_PROFILES_ENABLED"),
            default=False,
        ),
        repo_context_root=repo_context_root,
        agent_session_dir=_default_agent_session_dir(repo_context_root),
        repo_context_max_files=int(os.getenv("BIBER_REPO_CONTEXT_MAX_FILES", "12")),
        repo_context_max_bytes_per_file=int(
            os.getenv("BIBER_REPO_CONTEXT_MAX_BYTES_PER_FILE", "12000")
        ),
        repo_context_max_total_bytes=int(os.getenv("BIBER_REPO_CONTEXT_MAX_TOTAL_BYTES", "40000")),
        xriq_workspace_dir=os.getenv("BIBER_XRIQ_WORKSPACE_DIR")
        or os.path.join(repo_context_root, "xriq"),
        xriq_node_command=os.getenv(
            "BIBER_XRIQ_NODE_COMMAND",
            "cargo run -q -p xriq-node --",
        ),
        xriq_chain_file=os.getenv(
            "BIBER_XRIQ_CHAIN_FILE",
            "target/biber-xriq-private-devnet-chain.bin",
        ),
        xriq_pending_file=os.getenv(
            "BIBER_XRIQ_PENDING_FILE",
            "target/biber-xriq-private-devnet-pending.tsv",
        ),
        xriq_snapshot_root_dir=os.getenv(
            "BIBER_XRIQ_SNAPSHOT_ROOT_DIR",
            "target/biber-xriq-private-devnet-snapshots",
        ),
        xriq_snapshot_import_root_dir=os.getenv(
            "BIBER_XRIQ_SNAPSHOT_IMPORT_ROOT_DIR",
            "target/biber-xriq-private-devnet-imports",
        ),
        xriq_default_alice_balance_base_units=os.getenv(
            "BIBER_XRIQ_DEFAULT_ALICE_BALANCE_BASE_UNITS",
            "100",
        ),
        xriq_command_timeout_seconds=float(
            os.getenv("BIBER_XRIQ_COMMAND_TIMEOUT_SECONDS", "30")
        ),
        xriq_rustup_home=os.getenv("BIBER_XRIQ_RUSTUP_HOME") or None,
        xriq_cargo_home=os.getenv("BIBER_XRIQ_CARGO_HOME") or None,
        xriq_path_prefix=os.getenv("BIBER_XRIQ_PATH_PREFIX") or None,
        test_runner_timeout_seconds=float(
            os.getenv("BIBER_TEST_RUNNER_TIMEOUT_SECONDS", "120")
        ),
        test_runner_max_output_bytes=int(
            os.getenv("BIBER_TEST_RUNNER_MAX_OUTPUT_BYTES", "12000")
        ),
        workspace_edit_max_file_bytes=int(
            os.getenv("BIBER_WORKSPACE_EDIT_MAX_FILE_BYTES", "200000")
        ),
        workspace_edit_max_new_text_bytes=int(
            os.getenv("BIBER_WORKSPACE_EDIT_MAX_NEW_TEXT_BYTES", "120000")
        ),
    )

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


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
            passcodes[passcode] = int(priority or "3")
        except ValueError:
            passcodes[passcode] = 3
    return passcodes


@dataclass
class Settings:
    env: str = os.getenv("BIBER_ENV", "dev")
    admin_username: str = os.getenv("BIBER_ADMIN_USERNAME", "biber_admin")
    admin_password: str = os.getenv("BIBER_ADMIN_PASSWORD", "ChangeMeImmediately!123")
    demo_api_key: str = os.getenv("BIBER_DEMO_API_KEY", "dev-api-key-change-me")
    api_keys: tuple[str, ...] = _csv(os.getenv("BIBER_API_KEYS"))

    passcode_full_gpu: str = os.getenv("BIBER_PASSCODE_FULL_GPU", "BIBER_FULL_GPU_DEMO")
    passcode_20_gpu: str = os.getenv("BIBER_PASSCODE_20_GPU", "BIBER_20_GPU_DEMO")
    passcode_queue_priority: str = os.getenv("BIBER_PASSCODE_QUEUE_PRIORITY", "BIBER_QUEUE_PRIORITY_DEMO")
    priority_passcodes: dict[str, int] = None

    default_model: str = os.getenv("BIBER_DEFAULT_MODEL", "biber-dev-core")
    chat_mode: str = os.getenv("BIBER_CHAT_MODE", "infer")

    local_model_base_url: str = os.getenv("BIBER_LOCAL_MODEL_BASE_URL", "http://localhost:8000/v1")
    local_model_name: str = os.getenv("BIBER_LOCAL_MODEL_NAME", "biber-dev-core")
    local_model_timeout_seconds: float = float(os.getenv("BIBER_LOCAL_MODEL_TIMEOUT_SECONDS", "180"))

    mentor_enabled: bool = _bool(os.getenv("BIBER_MENTOR_ENABLED"), default=False)
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    openai_model: str | None = os.getenv("OPENAI_MODEL") or None

    github_token: str | None = os.getenv("GITHUB_TOKEN") or None
    github_default_owner: str | None = os.getenv("GITHUB_DEFAULT_OWNER") or None
    github_default_repo: str | None = os.getenv("GITHUB_DEFAULT_REPO") or None

    azure_storage_connection_string: str | None = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or None
    azure_blob_container: str = os.getenv("AZURE_BLOB_CONTAINER", "biber-backups")

    def __post_init__(self):
        if self.priority_passcodes is None:
            self.priority_passcodes = _priority_passcodes(os.getenv("BIBER_PRIORITY_PASSCODES"))

settings = Settings()

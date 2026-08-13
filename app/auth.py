from fastapi import Header, HTTPException
from app.api_key_store import api_key_id, find_active_record_for_key, load_key_store
from app.config import settings


def _store_has_records(path: str) -> bool:
    if not path:
        return False
    return any(isinstance(record, dict) for record in load_key_store(path)["keys"])


def get_priority_from_passcode(passcode: str | None) -> int:
    if not passcode:
        return 3

    if passcode in settings.priority_passcodes:
        return settings.priority_passcodes[passcode]

    if passcode == settings.passcode_full_gpu:
        return 0
    if passcode == settings.passcode_20_gpu:
        return 1
    if passcode == settings.passcode_queue_priority:
        return 2

    return 3

def require_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    configured_keys = set(settings.api_keys)
    if settings.demo_api_key:
        configured_keys.add(settings.demo_api_key)
    has_key_source = bool(configured_keys) or _store_has_records(settings.api_key_store_path)

    if not has_key_source:
        if settings.env != "dev":
            raise HTTPException(status_code=503, detail="BIBER API keys are not configured")
        return {"api_key_id": "dev-no-key-configured", "user_id": "dev_user"}

    api_key = x_api_key
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.replace("Bearer ", "").strip()

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    if api_key in configured_keys:
        return {"api_key_id": api_key_id(api_key), "user_id": "env_key"}

    record = find_active_record_for_key(settings.api_key_store_path, api_key)
    if record is not None:
        return {
            "api_key_id": str(record.get("key_id") or api_key_id(api_key)),
            "user_id": str(record.get("user_id") or "api_user"),
        }

    if api_key not in configured_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return {"api_key_id": api_key_id(api_key), "user_id": "env_key"}


def require_admin_api_key(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
):
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=503,
            detail="BIBER_ADMIN_API_KEY must be configured before admin key management",
        )

    api_key = x_api_key
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.replace("Bearer ", "").strip()

    if api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid admin API key")
    return {"api_key_id": api_key_id(api_key), "role": "admin"}

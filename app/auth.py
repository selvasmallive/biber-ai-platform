from hashlib import sha256

from fastapi import Header, HTTPException
from app.config import settings


def _key_id(api_key: str) -> str:
    return sha256(api_key.encode("utf-8")).hexdigest()[:12]


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

    if not configured_keys:
        if settings.env != "dev":
            raise HTTPException(status_code=503, detail="BIBER API keys are not configured")
        return {"api_key_id": "dev-no-key-configured", "user_id": "dev_user"}

    api_key = x_api_key
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.replace("Bearer ", "").strip()

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if api_key not in configured_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return {"api_key_id": _key_id(api_key), "user_id": "demo_user"}

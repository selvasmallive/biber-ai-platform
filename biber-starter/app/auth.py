from fastapi import Header, HTTPException
from app.config import settings

def get_priority_from_passcode(passcode: str | None) -> int:
    if not passcode:
        return 3

    if passcode == settings.passcode_full_gpu:
        return 0
    if passcode == settings.passcode_20_gpu:
        return 1
    if passcode == settings.passcode_queue_priority:
        return 2

    return 3

def require_api_key(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing API key")

    api_key = authorization.replace("Bearer ", "").strip()
    if api_key != settings.demo_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return {"api_key_id": "demo", "user_id": "demo_user"}

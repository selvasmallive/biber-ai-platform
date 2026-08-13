from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from .api_key_store import api_key_id, find_active_record_for_key, load_key_store
from .config import BiberSettings, get_settings


@dataclass(frozen=True)
class AuthContext:
    api_key_id: str
    priority: int
    user_id: str = "api_user"


@dataclass(frozen=True)
class AdminAuthContext:
    api_key_id: str
    role: str = "admin"


def _extract_api_key(request: Request) -> str | None:
    api_key = request.headers.get("x-api-key")
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.removeprefix("Bearer ").strip()
    return api_key


def _store_has_records(path: str) -> bool:
    if not path:
        return False
    return any(isinstance(record, dict) for record in load_key_store(path)["keys"])


async def require_api_key(
    request: Request,
    settings: BiberSettings = Depends(get_settings),
) -> AuthContext:
    has_key_source = bool(settings.api_keys) or _store_has_records(settings.api_key_store_path)
    if not has_key_source:
        if settings.env != "dev":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="BIBER_API_KEYS or BIBER_API_KEY_STORE_PATH must be configured.",
            )
        return AuthContext(api_key_id="dev-no-key-configured", priority=0)

    api_key = _extract_api_key(request)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key.",
        )

    passcode = request.headers.get("x-biber-passcode")
    priority = settings.priority_passcodes.get(passcode or "", 0)
    if api_key in settings.api_keys:
        return AuthContext(api_key_id=api_key_id(api_key), priority=priority, user_id="env_key")

    record = find_active_record_for_key(settings.api_key_store_path, api_key)
    if record is not None:
        return AuthContext(
            api_key_id=str(record.get("key_id") or api_key_id(api_key)),
            priority=priority,
            user_id=str(record.get("user_id") or "api_user"),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid API key.",
    )


async def require_admin_api_key(
    request: Request,
    settings: BiberSettings = Depends(get_settings),
) -> AdminAuthContext:
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BIBER_ADMIN_API_KEY must be configured before admin key management.",
        )

    api_key = _extract_api_key(request)
    if api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid admin API key.",
        )
    return AdminAuthContext(api_key_id=api_key_id(api_key))

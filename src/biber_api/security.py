from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from fastapi import Depends, HTTPException, Request, status

from .config import BiberSettings, get_settings


@dataclass(frozen=True)
class AuthContext:
    api_key_id: str
    priority: int


def _key_id(api_key: str) -> str:
    return sha256(api_key.encode("utf-8")).hexdigest()[:12]


async def require_api_key(
    request: Request,
    settings: BiberSettings = Depends(get_settings),
) -> AuthContext:
    if not settings.api_keys:
        if settings.env != "dev":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="BIBER_API_KEYS must be configured before enabling protected endpoints.",
            )
        return AuthContext(api_key_id="dev-no-key-configured", priority=0)

    api_key = request.headers.get("x-api-key")
    if api_key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid x-api-key.",
        )

    passcode = request.headers.get("x-biber-passcode")
    priority = settings.priority_passcodes.get(passcode or "", 0)
    return AuthContext(api_key_id=_key_id(api_key), priority=priority)

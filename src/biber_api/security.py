from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from time import monotonic

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


@dataclass(frozen=True)
class RequestGuardDecision:
    status_code: int
    detail: str
    headers: dict[str, str]


_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
_RATE_LIMIT_MAX_IDENTITIES = 10000


def _extract_api_key(request: Request) -> str | None:
    api_key = request.headers.get("x-api-key")
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.removeprefix("Bearer ").strip()
    return api_key


def _extract_content_length(request: Request) -> int | None:
    raw_value = request.headers.get("content-length")
    if raw_value is None:
        return None
    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _request_guard_identity(request: Request) -> str:
    api_key = _extract_api_key(request)
    if api_key:
        return f"key:{api_key_id(api_key)}"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return f"ip:{forwarded_for.split(',', 1)[0].strip()}"
    if request.client and request.client.host:
        return f"ip:{request.client.host}"
    return "ip:unknown"


def clear_api_request_guard_state() -> None:
    _RATE_LIMIT_BUCKETS.clear()


def check_api_request_guard(
    request: Request,
    settings: BiberSettings,
) -> RequestGuardDecision | None:
    if not settings.api_guard_enabled or not request.url.path.startswith("/v1/"):
        return None

    max_request_bytes = settings.api_max_request_bytes
    content_length = _extract_content_length(request)
    if (
        max_request_bytes > 0
        and content_length is not None
        and content_length > max_request_bytes
    ):
        return RequestGuardDecision(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="BIBER API request body is too large.",
            headers={
                "X-BIBER-Max-Request-Bytes": str(max_request_bytes),
            },
        )

    limit = settings.api_rate_limit_requests_per_minute
    if limit <= 0:
        return None

    now = monotonic()
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    identity = _request_guard_identity(request)
    bucket = _RATE_LIMIT_BUCKETS.setdefault(identity, [])
    while bucket and bucket[0] < window_start:
        bucket.pop(0)
    if len(_RATE_LIMIT_BUCKETS) > _RATE_LIMIT_MAX_IDENTITIES:
        for key, timestamps in list(_RATE_LIMIT_BUCKETS.items()):
            if not timestamps or timestamps[-1] < window_start:
                _RATE_LIMIT_BUCKETS.pop(key, None)

    if len(bucket) >= limit:
        retry_after = max(1, ceil(bucket[0] + _RATE_LIMIT_WINDOW_SECONDS - now))
        return RequestGuardDecision(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="BIBER API request rate limit exceeded.",
            headers={
                "Retry-After": str(retry_after),
                "X-BIBER-RateLimit-Limit": str(limit),
            },
        )

    bucket.append(now)
    return None


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

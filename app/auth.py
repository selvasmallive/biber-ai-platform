from dataclasses import dataclass
from math import ceil
from time import monotonic

from fastapi import Header, HTTPException, Request, status
from app.api_key_store import api_key_id, find_active_record_for_key, load_key_store
from app.config import settings


@dataclass(frozen=True)
class RequestGuardDecision:
    status_code: int
    detail: str
    headers: dict[str, str]


_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
_RATE_LIMIT_MAX_IDENTITIES = 10000


def _extract_api_key_from_request(request: Request) -> str | None:
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
    api_key = _extract_api_key_from_request(request)
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


def check_api_request_guard(request: Request) -> RequestGuardDecision | None:
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
            headers={"X-BIBER-Max-Request-Bytes": str(max_request_bytes)},
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

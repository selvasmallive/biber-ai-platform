from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


STORE_VERSION = 1


def api_key_id(api_key: str) -> str:
    return sha256(api_key.encode("utf-8")).hexdigest()[:12]


def api_key_hash(api_key: str) -> str:
    return sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"biber_{secrets.token_urlsafe(32)}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _store_path(path: str) -> Path:
    return Path(path).expanduser()


def _empty_store() -> dict[str, Any]:
    return {"version": STORE_VERSION, "keys": []}


def load_key_store(path: str) -> dict[str, Any]:
    if not path:
        return _empty_store()
    store_path = _store_path(path)
    if not store_path.exists():
        return _empty_store()
    try:
        payload = json.loads(store_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_store()
    if not isinstance(payload, dict):
        return _empty_store()
    keys = payload.get("keys")
    if not isinstance(keys, list):
        keys = []
    return {"version": payload.get("version", STORE_VERSION), "keys": keys}


def save_key_store(path: str, payload: dict[str, Any]) -> None:
    if not path:
        raise ValueError("API key store path is not configured.")
    store_path = _store_path(path)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = store_path.with_suffix(f"{store_path.suffix}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(store_path)


def public_key_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key_id": str(record.get("key_id") or ""),
        "user_id": str(record.get("user_id") or ""),
        "label": str(record.get("label") or ""),
        "created_at": record.get("created_at"),
        "revoked_at": record.get("revoked_at"),
        "active": record.get("revoked_at") in (None, ""),
    }


def list_public_key_records(path: str) -> list[dict[str, Any]]:
    return [public_key_record(record) for record in load_key_store(path)["keys"]]


def find_active_record_for_key(path: str, api_key: str) -> dict[str, Any] | None:
    wanted_hash = api_key_hash(api_key)
    for record in load_key_store(path)["keys"]:
        if not isinstance(record, dict):
            continue
        if record.get("key_hash") != wanted_hash:
            continue
        if record.get("revoked_at"):
            return None
        return record
    return None


def issue_api_key(path: str, *, user_id: str, label: str = "") -> dict[str, Any]:
    api_key = generate_api_key()
    record = {
        "key_id": api_key_id(api_key),
        "key_hash": api_key_hash(api_key),
        "user_id": user_id,
        "label": label,
        "created_at": _now(),
        "revoked_at": None,
    }
    payload = load_key_store(path)
    payload["keys"].append(record)
    save_key_store(path, payload)
    return {"api_key": api_key, "record": public_key_record(record)}


def revoke_api_key(path: str, key_id: str) -> dict[str, Any] | None:
    payload = load_key_store(path)
    for record in payload["keys"]:
        if not isinstance(record, dict):
            continue
        if record.get("key_id") != key_id:
            continue
        if not record.get("revoked_at"):
            record["revoked_at"] = _now()
            save_key_store(path, payload)
        return public_key_record(record)
    return None

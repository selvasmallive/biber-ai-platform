from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class AgentSessionStoreError(Exception):
    """Raised when a persisted agent session cannot be stored or read."""


def _store_dir(settings: Any) -> Path:
    root = Path(settings.agent_session_dir)
    if not root.is_absolute():
        root = Path(settings.repo_context_root) / root
    return root


def _safe_session_id(session_id: str) -> str:
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise AgentSessionStoreError("Invalid agent session id.")
    return session_id


def _session_path(settings: Any, session_id: str) -> Path:
    return _store_dir(settings) / f"{_safe_session_id(session_id)}.json"


def persist_agent_session(response: Any, settings: Any) -> dict[str, object]:
    root = _store_dir(settings)
    path = _session_path(settings, response.id)
    payload = response.model_dump(mode="json")
    payload["artifact_path"] = str(path)
    tmp_path = path.with_suffix(".json.tmp")
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_path, path)
    except OSError as exc:
        raise AgentSessionStoreError(f"Could not persist agent session: {exc}") from exc
    return {
        "id": response.id,
        "created_at": response.created_at,
        "model": response.model,
        "mentor_used": response.mentor_used,
        "steps": [step.name for step in response.steps],
        "artifact_path": str(path),
    }


def load_agent_session(session_id: str, settings: Any) -> dict[str, Any]:
    path = _session_path(settings, session_id)
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise AgentSessionStoreError("Agent session not found.") from exc
    except json.JSONDecodeError as exc:
        raise AgentSessionStoreError("Agent session artifact is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise AgentSessionStoreError("Agent session artifact is not a JSON object.")
    if payload.get("id") != session_id:
        raise AgentSessionStoreError("Agent session artifact id mismatch.")
    return payload


def list_agent_sessions(settings: Any, *, limit: int = 20) -> list[dict[str, object]]:
    root = _store_dir(settings)
    if not root.exists():
        return []
    sessions: list[dict[str, object]] = []
    for path in sorted(
        root.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        if len(sessions) >= limit:
            break
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            continue
        steps = payload.get("steps")
        step_names: list[str] = []
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict) and isinstance(step.get("name"), str):
                    step_names.append(step["name"])
        sessions.append(
            {
                "id": payload["id"],
                "created_at": payload.get("created_at"),
                "model": payload.get("model"),
                "mentor_used": payload.get("mentor_used"),
                "steps": step_names,
                "artifact_path": str(path),
            }
        )
    return sessions

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


STABLE_MODEL_ID = "biber-dev-core-v1"
CANDIDATE_MODEL_ID = "biber-dev-core-v2-candidate"
OPENAI_COMPATIBLE_CHAT = "openai-compatible-chat"


class ModelRegistryError(ValueError):
    pass


class UnknownModelError(ModelRegistryError):
    pass


class DisabledModelError(ModelRegistryError):
    pass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    lifecycle: str
    provider_id: str
    provider_type: str
    base_url: str
    provider_model: str
    upstream_model: str
    enabled: bool
    aliases: tuple[str, ...] = ()

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "lifecycle": self.lifecycle,
            "provider_id": self.provider_id,
            "provider_type": self.provider_type,
            "base_url": self.base_url,
            "provider_model": self.provider_model,
            "upstream_model": self.upstream_model,
            "enabled": self.enabled,
            "aliases": list(self.aliases),
        }


@dataclass(frozen=True)
class ModelRegistry:
    models: tuple[ModelSpec, ...]
    default_model: str
    stable_model: str
    candidate_model: str

    def resolve(self, model_id: str | None) -> ModelSpec:
        requested = model_id or self.default_model
        for model in self.models:
            if requested == model.id or requested in model.aliases:
                if not model.enabled:
                    raise DisabledModelError(f"Model is configured but disabled: {model.id}")
                return model
        raise UnknownModelError(f"Unknown model: {requested}")

    def canonical_id(self, model_id: str | None) -> str:
        return self.resolve(model_id).id

    def as_response(self) -> dict[str, Any]:
        return {
            "object": "list",
            "default_model": self._canonical_or_raw(self.default_model),
            "stable_model": self._canonical_or_raw(self.stable_model),
            "candidate_model": self.candidate_model,
            "models": [model.public_dict() for model in self.models],
        }

    def _canonical_or_raw(self, model_id: str) -> str:
        for model in self.models:
            if model_id == model.id or model_id in model.aliases:
                return model.id
        return model_id


def build_model_registry(settings: Any) -> ModelRegistry:
    raw_registry = os.getenv("BIBER_MODEL_REGISTRY_JSON")
    if raw_registry:
        return _registry_from_json(raw_registry)

    stable_id = os.getenv("BIBER_STABLE_MODEL_ID", STABLE_MODEL_ID)
    candidate_id = os.getenv("BIBER_CANDIDATE_MODEL_ID", CANDIDATE_MODEL_ID)
    default_model = getattr(settings, "default_model", None) or os.getenv(
        "BIBER_DEFAULT_MODEL", stable_id
    )
    local_base_url = getattr(settings, "local_model_base_url")
    local_model_name = getattr(settings, "local_model_name")
    candidate_base_url = os.getenv("BIBER_CANDIDATE_MODEL_BASE_URL") or local_base_url
    candidate_provider_model = (
        os.getenv("BIBER_CANDIDATE_PROVIDER_MODEL")
        or os.getenv("BIBER_CANDIDATE_MODEL_NAME")
        or candidate_id
    )

    stable = ModelSpec(
        id=stable_id,
        label="BIBER dev core v1",
        lifecycle="stable",
        provider_id=os.getenv("BIBER_LOCAL_PROVIDER_ID", "vast-vllm"),
        provider_type=OPENAI_COMPATIBLE_CHAT,
        base_url=local_base_url,
        provider_model=local_model_name,
        upstream_model=os.getenv(
            "BIBER_STABLE_UPSTREAM_MODEL",
            os.getenv("BIBER_HF_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct"),
        ),
        enabled=True,
        aliases=_csv_env("BIBER_STABLE_MODEL_ALIASES", ("biber-dev-core", local_model_name)),
    )
    candidate = ModelSpec(
        id=candidate_id,
        label="BIBER dev core v2 candidate",
        lifecycle="candidate",
        provider_id=os.getenv("BIBER_CANDIDATE_PROVIDER_ID", "vast-vllm-candidate"),
        provider_type=OPENAI_COMPATIBLE_CHAT,
        base_url=candidate_base_url,
        provider_model=candidate_provider_model,
        upstream_model=os.getenv("BIBER_CANDIDATE_UPSTREAM_MODEL", "Qwen/Qwen3-Coder-Next"),
        enabled=_bool(os.getenv("BIBER_CANDIDATE_MODEL_ENABLED"), default=False),
        aliases=_csv_env("BIBER_CANDIDATE_MODEL_ALIASES", ()),
    )

    return ModelRegistry(
        models=(stable, candidate),
        default_model=default_model,
        stable_model=stable.id,
        candidate_model=candidate.id,
    )


def _registry_from_json(raw_registry: str) -> ModelRegistry:
    data = json.loads(raw_registry)
    models = tuple(_model_from_dict(item) for item in data.get("models", []))
    if not models:
        raise ModelRegistryError("BIBER_MODEL_REGISTRY_JSON must include at least one model")
    default_model = data.get("default_model") or models[0].id
    stable_model = data.get("stable_model") or default_model
    candidate_model = data.get("candidate_model") or CANDIDATE_MODEL_ID
    return ModelRegistry(
        models=models,
        default_model=default_model,
        stable_model=stable_model,
        candidate_model=candidate_model,
    )


def _model_from_dict(data: dict[str, Any]) -> ModelSpec:
    return ModelSpec(
        id=data["id"],
        label=data.get("label", data["id"]),
        lifecycle=data.get("lifecycle", "stable"),
        provider_id=data.get("provider_id", "vast-vllm"),
        provider_type=data.get("provider_type", OPENAI_COMPATIBLE_CHAT),
        base_url=data["base_url"],
        provider_model=data["provider_model"],
        upstream_model=data.get("upstream_model", data["provider_model"]),
        enabled=bool(data.get("enabled", True)),
        aliases=tuple(data.get("aliases", ())),
    )


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(key)
    if not value:
        return tuple(dict.fromkeys(item for item in default if item))
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return tuple(dict.fromkeys(items))

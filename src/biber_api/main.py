from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException

from .azure_backup import AzureBackupDisabled, AzureBlobBackup
from .config import BiberSettings, get_settings
from .github import (
    GitHubClient,
    GitHubConfigurationError,
    GitHubDisabled,
    GitHubSaveError,
)
from .llm import BiberChatService, MENTOR_TRIGGER_PHRASE
from .schemas import (
    AzureBackupRequest,
    AzureBackupResponse,
    ChatRequest,
    ChatResponse,
    RuntimeStatus,
    SaveToGitHubRequest,
    SaveToGitHubResponse,
)
from .security import AuthContext, require_api_key


app = FastAPI(
    title="BIBER API",
    version="0.1.0",
    description="Phase 1 API for biber-dev-core local GPU inference.",
)


@app.get("/health")
async def health(settings: BiberSettings = Depends(get_settings)) -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "biber-api",
        "env": settings.env,
        "local_model_name": settings.local_model_name,
        "mentor_configured": settings.mentor_enabled
        and bool(settings.openai_api_key)
        and bool(settings.openai_model),
    }


@app.get("/v1/runtime", response_model=RuntimeStatus)
async def runtime_status(settings: BiberSettings = Depends(get_settings)) -> RuntimeStatus:
    return RuntimeStatus(
        service="biber-api",
        local_model_name=settings.local_model_name,
        local_model_base_url=settings.local_model_base_url,
        mentor_enabled=settings.mentor_enabled,
        mentor_configured=bool(settings.openai_api_key and settings.openai_model),
        mentor_trigger_phrase=MENTOR_TRIGGER_PHRASE,
        github_configured=bool(settings.github_token),
        azure_backup_configured=bool(settings.azure_storage_connection_string),
    )


@app.post("/v1/chat", response_model=ChatResponse)
async def chat_completion(
    request_body: ChatRequest,
    auth: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> ChatResponse:
    service = BiberChatService(settings)
    github = GitHubClient(settings)
    backup = AzureBlobBackup(settings)
    created_at = datetime.now(UTC).isoformat()

    try:
        content, mentor_notes, raw = await service.generate(request_body)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Model endpoint returned {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model endpoint failed: {exc}") from exc

    github_url = None
    if request_body.save_to_github:
        try:
            github_url = await github.save_text(request_body.save_to_github, content)
        except GitHubDisabled as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except GitHubConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except GitHubSaveError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    azure_blob_url = None
    if request_body.backup_to_azure:
        try:
            azure_blob_url = await backup.upload_json(
                f"chat/{created_at.replace(':', '-')}-{uuid4()}.json",
                {
                    "request": request_body.model_dump(mode="json"),
                    "response": content,
                    "mentor_notes": mentor_notes,
                    "model_raw": raw,
                    "auth": {"api_key_id": auth.api_key_id, "priority": auth.priority},
                },
            )
        except AzureBackupDisabled as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(
        id=str(uuid4()),
        created_at=created_at,
        model=settings.local_model_name,
        content=content,
        mentor_used=mentor_notes is not None,
        mentor_notes=mentor_notes,
        github_url=github_url,
        azure_blob_url=azure_blob_url,
        priority=auth.priority,
    )


@app.post("/v1/save/github", response_model=SaveToGitHubResponse)
async def save_to_github(
    request_body: SaveToGitHubRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> SaveToGitHubResponse:
    try:
        url = await GitHubClient(settings).save_text(request_body.target, request_body.content)
    except GitHubDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GitHubConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubSaveError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SaveToGitHubResponse(url=url)


@app.post("/v1/backup/azure", response_model=AzureBackupResponse)
async def backup_to_azure(
    request_body: AzureBackupRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> AzureBackupResponse:
    try:
        url = await AzureBlobBackup(settings).upload_json(
            request_body.blob_name,
            request_body.payload,
        )
    except AzureBackupDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AzureBackupResponse(url=url)

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.azure_backup import AzureBackupDisabled, AzureBlobBackup
from app.auth import require_api_key, get_priority_from_passcode
from app.config import settings
from app.github_client import (
    GitHubClient,
    GitHubConfigurationError,
    GitHubDisabled,
    GitHubSaveError,
    GitHubSaveTarget,
)
from app.llm import BiberChatService
from app.scheduler import scheduler

app = FastAPI(
    title="BIBER AI Platform",
    version="0.1.0",
    description="Private GPU-backed BIBER AI platform"
)


Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class GitHubSaveTargetRequest(BaseModel):
    path: str = Field(min_length=1)
    owner: str | None = None
    repo: str | None = None
    branch: str = "main"
    commit_message: str = "Save BIBER generated code"


class ChatRequest(BaseModel):
    message: str | None = None
    messages: list[ChatMessage] | None = None
    model: str | None = None
    language: str | None = None
    task_type: str = "code_generation"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0, le=32000)
    use_mentor: bool = True
    queue_only: bool = False
    save_to_github: GitHubSaveTargetRequest | None = None
    backup_to_azure: bool = False

    def normalized_messages(self) -> list[dict[str, str]]:
        if self.messages:
            return [message.model_dump() for message in self.messages]
        if self.message:
            return [{"role": "user", "content": self.message}]
        raise ValueError("Either message or messages is required.")


class ChatResponse(BaseModel):
    id: str
    created_at: str
    model: str
    content: str
    mentor_used: bool
    mentor_notes: str | None = None
    github_url: str | None = None
    azure_blob_url: str | None = None
    priority: int


class CodeRequest(BaseModel):
    prompt: str
    language: str
    model: str | None = None

class VideoRequest(BaseModel):
    prompt: str
    video_path: str | None = None
    model: str | None = "biber-video-core"

class AudioRequest(BaseModel):
    prompt: str
    audio_path: str | None = None
    model: str | None = "biber-audio-core"

class ProctorAnalyzeRequest(BaseModel):
    session_id: str
    prompt: str | None = "Analyze proctoring session"
    model: str | None = "biber-proctor-core"


class SaveToGitHubRequest(BaseModel):
    target: GitHubSaveTargetRequest
    content: str = Field(min_length=1)


class SaveToGitHubResponse(BaseModel):
    url: str


class AzureBackupRequest(BaseModel):
    blob_name: str = Field(min_length=1)
    payload: dict[str, Any]


class AzureBackupResponse(BaseModel):
    url: str


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "biber-api",
        "env": settings.env,
        "local_model_name": settings.local_model_name,
    }


@app.get("/v1/runtime")
def runtime_status(auth=Depends(require_api_key)):
    return {
        "service": "biber-api",
        "local_model_name": settings.local_model_name,
        "local_model_base_url": settings.local_model_base_url,
        "chat_mode": settings.chat_mode,
        "mentor_enabled": settings.mentor_enabled,
        "mentor_configured": bool(settings.openai_api_key and settings.openai_model),
        "github_configured": bool(settings.github_token),
        "azure_backup_configured": bool(settings.azure_storage_connection_string),
    }

@app.get("/v1/models")
def models(auth=Depends(require_api_key)):
    return {
        "models": [
            "biber-dev-core",
            "biber-code-python",
            "biber-code-react",
            "biber-code-dotnet",
            "biber-code-java",
            "biber-code-rust",
            "biber-video-core",
            "biber-audio-core",
            "biber-proctor-core"
        ]
    }

@app.post("/v1/chat")
async def chat(
    req: ChatRequest,
    x_biber_passcode: str | None = Header(default=None),
    auth=Depends(require_api_key),
):
    priority = get_priority_from_passcode(x_biber_passcode)
    if req.queue_only or settings.chat_mode == "queue":
        job = scheduler.submit(req.model or settings.default_model, "chat", req.model_dump(), priority)
        return {
            "job_id": job.job_id,
            "status": job.status,
            "priority": priority,
            "message": "Job accepted. Worker integration is starter placeholder."
        }

    try:
        messages = req.normalized_messages()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    created_at = datetime.now(UTC).isoformat()
    try:
        content, mentor_notes, raw = await BiberChatService().generate(
            messages=messages,
            language=req.language,
            task_type=req.task_type,
            use_mentor=req.use_mentor,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Model endpoint returned {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model endpoint failed: {exc}") from exc

    github_url = None
    if req.save_to_github:
        target = GitHubSaveTarget(**req.save_to_github.model_dump())
        try:
            github_url = await GitHubClient().save_text(target, content)
        except GitHubDisabled as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except GitHubConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except GitHubSaveError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    azure_blob_url = None
    if req.backup_to_azure:
        try:
            azure_blob_url = await AzureBlobBackup().upload_json(
                f"chat/{created_at.replace(':', '-')}-{uuid4()}.json",
                {
                    "request": req.model_dump(mode="json"),
                    "response": content,
                    "mentor_notes": mentor_notes,
                    "model_raw": raw,
                    "auth": auth,
                },
            )
        except AzureBackupDisabled as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(
        id=str(uuid4()),
        created_at=created_at,
        model=req.model or settings.local_model_name,
        content=content,
        mentor_used=mentor_notes is not None,
        mentor_notes=mentor_notes,
        github_url=github_url,
        azure_blob_url=azure_blob_url,
        priority=priority,
    )

@app.post("/v1/code")
def code(req: CodeRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-dev-core", "code", req.model_dump(), priority)
    return {"job_id": job.job_id, "status": job.status, "priority": priority}

@app.post("/v1/video")
def video(req: VideoRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-video-core", "video", req.model_dump(), priority)
    return {"job_id": job.job_id, "status": job.status, "priority": priority}

@app.post("/v1/audio")
def audio(req: AudioRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-audio-core", "audio", req.model_dump(), priority)
    return {"job_id": job.job_id, "status": job.status, "priority": priority}

@app.post("/v1/proctor/session/analyze")
def proctor_analyze(req: ProctorAnalyzeRequest, x_biber_passcode: str | None = Header(default=None), auth=Depends(require_api_key)):
    priority = get_priority_from_passcode(x_biber_passcode)
    job = scheduler.submit(req.model or "biber-proctor-core", "proctor", req.model_dump(), priority)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "priority": priority,
        "risk_policy": "AI output is advisory only. Allowed labels: clear, low_risk, review_required, high_priority_review. Human review is required before action."
    }

@app.post("/v1/proctor/session/upload")
async def upload_proctor_media(file: UploadFile = File(...), auth=Depends(require_api_key)):
    content = await file.read()
    safe_name = Path(file.filename or f"upload-{uuid4().hex}").name
    storage_root = Path("/storage")
    storage_root.mkdir(parents=True, exist_ok=True)
    path = storage_root / safe_name
    with path.open("wb") as f:
        f.write(content)
    return {"filename": safe_name, "stored_path": str(path), "bytes": len(content)}


@app.post("/v1/save/github", response_model=SaveToGitHubResponse)
async def save_to_github(req: SaveToGitHubRequest, auth=Depends(require_api_key)):
    try:
        url = await GitHubClient().save_text(
            GitHubSaveTarget(**req.target.model_dump()),
            req.content,
        )
    except GitHubDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GitHubConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubSaveError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SaveToGitHubResponse(url=url)


@app.post("/v1/backup/azure", response_model=AzureBackupResponse)
async def backup_to_azure(req: AzureBackupRequest, auth=Depends(require_api_key)):
    try:
        url = await AzureBlobBackup().upload_json(req.blob_name, req.payload)
    except AzureBackupDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AzureBackupResponse(url=url)

@app.get("/admin/jobs")
def admin_jobs():
    return {"jobs": [j.__dict__ | {"status": j.status.value, "created_at": j.created_at.isoformat()} for j in scheduler.list_jobs()]}

@app.get("/admin/gpu")
def admin_gpu():
    return {
        "message": "Use nvidia-smi on host for true GPU status. This is API placeholder.",
        "policy": {
            "level_0": "100% GPU",
            "level_1": "20% GPU",
            "level_2": "queue priority",
            "level_3": "standard"
        }
    }

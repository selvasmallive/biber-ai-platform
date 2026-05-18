from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Path as ApiPath,
    Query,
    UploadFile,
)
from pydantic import BaseModel, Field

from app.agent_sessions import (
    AgentSessionStoreError,
    list_agent_sessions,
    load_agent_session,
    persist_agent_session,
)
from app.azure_backup import AzureBackupDisabled, AzureBlobBackup
from app.auth import require_api_key, get_priority_from_passcode
from app.config import settings
from app.github_client import (
    GitHubClient,
    GitHubConfigurationError,
    GitHubDisabled,
    GitHubPullRequestError,
    GitHubPullRequestTarget,
    GitHubSaveError,
    GitHubSaveTarget,
)
from app.llm import BiberChatService, MENTOR_TRIGGER_PHRASE
from app.model_registry import ModelRegistryError, build_model_registry
from app.repo_context import RepoContextError
from app.scheduler import scheduler
from app.test_runner import (
    TestRunnerConfigurationError,
    UnknownTestCommandError,
    list_test_commands,
    run_test_command,
)
from app.workspace_edit import (
    WorkspaceEditConfigurationError,
    WorkspaceEditError,
    apply_workspace_edit,
)
from app.xriq_client import (
    SNAPSHOT_NAME_PATTERN,
    XriqCommandError,
    XriqCommandTimeout,
    XriqConfigurationError,
    XriqPreflightTransferRequest,
    XriqSnapshotExportRequest,
    XriqSnapshotImportRequest,
    XriqSnapshotStoreError,
    get_private_devnet_snapshot,
    list_private_devnet_snapshots,
    run_private_devnet_account_detail,
    run_private_devnet_block_detail,
    run_private_devnet_explorer_overview,
    run_private_devnet_mempool_detail,
    run_private_devnet_overview,
    run_private_devnet_preflight_transfer,
    run_private_devnet_snapshot_export,
    run_private_devnet_snapshot_import,
    run_private_devnet_status,
    run_private_devnet_transaction_detail,
)

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
    base_branch: str | None = None
    create_branch_if_missing: bool = False
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
    repo_context_paths: list[str] = Field(default_factory=list, max_length=12)
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


class CreateGitHubPullRequestRequest(BaseModel):
    owner: str | None = None
    repo: str | None = None
    head: str = Field(min_length=1)
    base: str = "main"
    title: str = Field(min_length=1)
    body: str = ""
    draft: bool = True


class CreateGitHubPullRequestResponse(BaseModel):
    url: str
    number: int | None = None


class AzureBackupRequest(BaseModel):
    blob_name: str = Field(min_length=1)
    payload: dict[str, Any]


class AzureBackupResponse(BaseModel):
    url: str


class TestRunRequest(BaseModel):
    test_id: str = Field(min_length=1)
    dry_run: bool = False


class TestRunResponse(BaseModel):
    test_id: str
    label: str
    description: str
    cwd: str
    command: list[str]
    timeout_seconds: float
    executed: bool
    ok: bool | None
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool


class WorkspaceEditRequest(BaseModel):
    path: str = Field(min_length=1)
    old_text: str | None = None
    new_text: str = ""
    expected_replacements: int = Field(default=1, ge=1, le=20)
    create_if_missing: bool = False
    dry_run: bool = False


class WorkspaceEditResponse(BaseModel):
    path: str
    created: bool
    dry_run: bool
    changed: bool
    replacements: int
    old_sha256: str | None
    new_sha256: str
    old_bytes: int
    new_bytes: int


class AgentSessionRequest(BaseModel):
    instruction: str = Field(min_length=1)
    model: str | None = None
    language: str | None = None
    task_type: str = "agent_session"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=512, gt=0, le=32000)
    use_mentor: bool = False
    repo_context_paths: list[str] = Field(default_factory=list, max_length=12)
    workspace_edit: WorkspaceEditRequest | None = None
    test_id: str | None = "python-compileall-api"
    test_dry_run: bool = False
    save_to_github: GitHubSaveTargetRequest | None = None
    pull_request: CreateGitHubPullRequestRequest | None = None


class AgentSessionStep(BaseModel):
    name: str
    status: str
    detail: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)


class AgentSessionResponse(BaseModel):
    id: str
    created_at: str
    model: str
    content: str
    mentor_used: bool
    mentor_notes: str | None = None
    steps: list[AgentSessionStep]
    github_url: str | None = None
    pull_request_url: str | None = None
    pull_request_number: int | None = None
    artifact_path: str | None = None
    priority: int


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
        "mentor_trigger_phrase": MENTOR_TRIGGER_PHRASE,
        "github_configured": bool(settings.github_token),
        "azure_backup_configured": bool(settings.azure_storage_connection_string),
    }

@app.get("/v1/models")
def models(auth=Depends(require_api_key)):
    return build_model_registry(settings).as_response()


@app.get("/v1/tests")
def list_tests(auth=Depends(require_api_key)):
    return {"commands": list_test_commands(settings)}


@app.post("/v1/tests/run", response_model=TestRunResponse)
def run_tests(req: TestRunRequest, auth=Depends(require_api_key)):
    try:
        result = run_test_command(req.test_id, settings, dry_run=req.dry_run)
    except UnknownTestCommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TestRunnerConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TestRunResponse.model_validate(result)


@app.post("/v1/files/edit", response_model=WorkspaceEditResponse)
def edit_workspace_file(req: WorkspaceEditRequest, auth=Depends(require_api_key)):
    try:
        result = apply_workspace_edit(
            path=req.path,
            old_text=req.old_text,
            new_text=req.new_text,
            expected_replacements=req.expected_replacements,
            create_if_missing=req.create_if_missing,
            dry_run=req.dry_run,
            settings=settings,
        )
    except WorkspaceEditConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkspaceEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceEditResponse.model_validate(result)


@app.get("/v1/agent/sessions")
def get_agent_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    auth=Depends(require_api_key),
):
    return {"sessions": list_agent_sessions(settings, limit=limit)}


@app.get("/v1/agent/sessions/{session_id}", response_model=AgentSessionResponse)
def get_agent_session(session_id: str, auth=Depends(require_api_key)):
    try:
        payload = load_agent_session(session_id, settings)
    except AgentSessionStoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AgentSessionResponse.model_validate(payload)


@app.post("/v1/agent/sessions", response_model=AgentSessionResponse)
async def run_agent_session(
    req: AgentSessionRequest,
    x_biber_passcode: str | None = Header(default=None),
    auth=Depends(require_api_key),
):
    priority = get_priority_from_passcode(x_biber_passcode)
    steps: list[AgentSessionStep] = []
    created_at = datetime.now(UTC).isoformat()

    try:
        content, mentor_notes, raw, model_id = await BiberChatService().generate(
            messages=[{"role": "user", "content": req.instruction}],
            language=req.language,
            task_type=req.task_type,
            use_mentor=req.use_mentor,
            model=req.model,
            repo_context_paths=req.repo_context_paths,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except ModelRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RepoContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Model endpoint returned {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model endpoint failed: {exc}") from exc

    steps.append(
        AgentSessionStep(
            name="chat",
            status="ok",
            output={
                "model": model_id,
                "mentor_used": mentor_notes is not None,
                "repo_context_files": len(req.repo_context_paths),
            },
        )
    )

    if req.workspace_edit is not None:
        try:
            edit_result = apply_workspace_edit(
                path=req.workspace_edit.path,
                old_text=req.workspace_edit.old_text,
                new_text=req.workspace_edit.new_text,
                expected_replacements=req.workspace_edit.expected_replacements,
                create_if_missing=req.workspace_edit.create_if_missing,
                dry_run=req.workspace_edit.dry_run,
                settings=settings,
            )
        except WorkspaceEditConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except WorkspaceEditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        steps.append(
            AgentSessionStep(
                name="workspace_edit",
                status="ok",
                output=WorkspaceEditResponse.model_validate(edit_result).model_dump(),
            )
        )

    if req.test_id:
        try:
            test_result = run_test_command(
                req.test_id,
                settings,
                dry_run=req.test_dry_run,
            )
        except UnknownTestCommandError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except TestRunnerConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        steps.append(
            AgentSessionStep(
                name="test_run",
                status="ok" if test_result.get("ok") is not False else "failed",
                output=TestRunResponse.model_validate(test_result).model_dump(),
            )
        )

    github_url = None
    pull_request_url = None
    pull_request_number = None
    github = GitHubClient()
    if req.save_to_github is not None:
        try:
            github_url = await github.save_text(
                GitHubSaveTarget(**req.save_to_github.model_dump()),
                content,
            )
        except GitHubDisabled as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except GitHubConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except GitHubSaveError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        steps.append(
            AgentSessionStep(
                name="github_save",
                status="ok",
                output={"url": github_url},
            )
        )

    if req.pull_request is not None:
        try:
            pr_result = await github.create_pull_request(
                GitHubPullRequestTarget(**req.pull_request.model_dump())
            )
        except GitHubDisabled as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except GitHubConfigurationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except GitHubPullRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        pull_request_url = str(pr_result.get("url") or "")
        number = pr_result.get("number")
        pull_request_number = number if isinstance(number, int) else None
        steps.append(
            AgentSessionStep(
                name="github_pull_request",
                status="ok",
                output={
                    "url": pull_request_url,
                    "number": pull_request_number,
                },
            )
        )

    response = AgentSessionResponse(
        id=str(uuid4()),
        created_at=created_at,
        model=model_id,
        content=content,
        mentor_used=mentor_notes is not None,
        mentor_notes=mentor_notes,
        steps=steps,
        github_url=github_url,
        pull_request_url=pull_request_url,
        pull_request_number=pull_request_number,
        priority=priority,
    )
    try:
        artifact = persist_agent_session(response, settings)
    except AgentSessionStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response.artifact_path = str(artifact["artifact_path"])
    return response


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
        content, mentor_notes, raw, model_id = await BiberChatService().generate(
            messages=messages,
            language=req.language,
            task_type=req.task_type,
            use_mentor=req.use_mentor,
            model=req.model,
            repo_context_paths=req.repo_context_paths,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
    except ModelRegistryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RepoContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        model=model_id,
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


@app.post("/v1/github/pull-request", response_model=CreateGitHubPullRequestResponse)
async def create_github_pull_request(
    req: CreateGitHubPullRequestRequest,
    auth=Depends(require_api_key),
):
    try:
        result = await GitHubClient().create_pull_request(
            GitHubPullRequestTarget(**req.model_dump())
        )
    except GitHubDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GitHubConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubPullRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CreateGitHubPullRequestResponse.model_validate(result)


@app.post("/v1/xriq/private-devnet/preflight-transfer")
def xriq_private_devnet_preflight_transfer(
    req: XriqPreflightTransferRequest,
    auth=Depends(require_api_key),
):
    try:
        return run_private_devnet_preflight_transfer(req, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/overview")
def xriq_private_devnet_overview(
    explorer_limit: int = Query(default=5, ge=1, le=100),
    snapshot_limit: int = Query(default=5, ge=1, le=100),
    auth=Depends(require_api_key),
):
    try:
        return run_private_devnet_overview(
            settings,
            explorer_limit=explorer_limit,
            snapshot_limit=snapshot_limit,
        )
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
    except XriqSnapshotStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/v1/xriq/private-devnet/status")
def xriq_private_devnet_status(auth=Depends(require_api_key)):
    try:
        return run_private_devnet_status(settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/explorer")
def xriq_private_devnet_explorer_overview(
    limit: int | None = Query(default=None, ge=1, le=100),
    auth=Depends(require_api_key),
):
    try:
        return run_private_devnet_explorer_overview(settings, limit=limit)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/blocks/{height}")
def xriq_private_devnet_block_detail(
    height: int = ApiPath(ge=0),
    auth=Depends(require_api_key),
):
    try:
        return run_private_devnet_block_detail(height, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/accounts/{address}")
def xriq_private_devnet_account_detail(address: str, auth=Depends(require_api_key)):
    try:
        return run_private_devnet_account_detail(address, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/transactions/{tx_hash}")
def xriq_private_devnet_transaction_detail(tx_hash: str, auth=Depends(require_api_key)):
    try:
        return run_private_devnet_transaction_detail(tx_hash, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/mempool")
def xriq_private_devnet_mempool_detail(auth=Depends(require_api_key)):
    try:
        return run_private_devnet_mempool_detail(settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.post("/v1/xriq/private-devnet/snapshots/export")
def xriq_private_devnet_snapshot_export(
    req: XriqSnapshotExportRequest,
    auth=Depends(require_api_key),
):
    try:
        return run_private_devnet_snapshot_export(req, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.post("/v1/xriq/private-devnet/snapshots/import")
def xriq_private_devnet_snapshot_import(
    req: XriqSnapshotImportRequest,
    auth=Depends(require_api_key),
):
    try:
        return run_private_devnet_snapshot_import(req, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/snapshots")
def xriq_private_devnet_snapshots(
    limit: int = Query(default=20, ge=1, le=100),
    auth=Depends(require_api_key),
):
    try:
        return list_private_devnet_snapshots(settings, limit=limit)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqSnapshotStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/v1/xriq/private-devnet/snapshots/{snapshot_name}")
def xriq_private_devnet_snapshot_detail(
    snapshot_name: str = ApiPath(pattern=SNAPSHOT_NAME_PATTERN),
    auth=Depends(require_api_key),
):
    try:
        return get_private_devnet_snapshot(snapshot_name, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqSnapshotStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


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

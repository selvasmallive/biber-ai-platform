from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi import Path as ApiPath
from fastapi.responses import HTMLResponse

from .agent_sessions import (
    AgentSessionStoreError,
    list_agent_sessions,
    load_agent_session,
    persist_agent_session,
)
from .azure_backup import AzureBackupDisabled, AzureBlobBackup
from .config import BiberSettings, get_settings
from .github import (
    GitHubClient,
    GitHubConfigurationError,
    GitHubDisabled,
    GitHubPullRequestError,
    GitHubSaveError,
)
from .llm import BiberChatService, MENTOR_TRIGGER_PHRASE
from .model_registry import ModelRegistryError, build_model_registry
from .repo_context import (
    RepoContextError,
    list_repo_context_stack_profiles,
    plan_repo_context,
)
from .schemas import (
    AgentSessionRequest,
    AgentSessionResponse,
    AgentSessionStep,
    AzureBackupRequest,
    AzureBackupResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CreateGitHubPullRequestRequest,
    CreateGitHubPullRequestResponse,
    RuntimeStatus,
    SaveToGitHubRequest,
    SaveToGitHubResponse,
    TestFailureDiagnosisRequest,
    TestFailureDiagnosisResponse,
    TestRunRequest,
    TestRunResponse,
    RepoContextPlanRequest,
    RepoContextPlanResponse,
    WorkspaceEditRequest,
    WorkspaceEditPlanRequest,
    WorkspaceEditPlanResponse,
    WorkspaceEditResponse,
)
from .security import AuthContext, require_api_key
from .test_runner import (
    TestRunnerConfigurationError,
    UnknownTestCommandError,
    list_test_commands,
    run_test_command,
)
from .test_diagnosis import SUPPORTED_STACKS, diagnose_test_failure
from .workspace_edit import (
    WorkspaceEditConfigurationError,
    WorkspaceEditError,
    apply_workspace_edit,
    plan_workspace_edits,
)
from .xriq_client import (
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
    title="BIBER API",
    version="0.1.0",
    description="Phase 1 API for biber-dev-core local GPU inference.",
)


def _read_xriq_dashboard_html() -> str:
    for parent in Path(__file__).resolve().parents:
        dashboard = parent / "examples" / "xriq_private_devnet_dashboard.html"
        if dashboard.is_file():
            return dashboard.read_text(encoding="utf-8")
    raise HTTPException(status_code=500, detail="XRIQ dashboard asset is missing.")


@app.get(
    "/xriq/private-devnet/dashboard",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def xriq_private_devnet_dashboard() -> HTMLResponse:
    return HTMLResponse(_read_xriq_dashboard_html())


def _format_xriq_agent_context(overview: dict[str, object]) -> str:
    summary_value = overview.get("summary")
    summary = summary_value if isinstance(summary_value, dict) else {}
    fields = [
        "XRIQ private-devnet context for this BIBER agent session.",
        f"current_height: {summary.get('current_height', 'unknown')}",
        f"state_root: {summary.get('state_root', 'unknown')}",
        f"pending_count: {summary.get('pending_count', 'unknown')}",
        f"snapshot_count: {summary.get('snapshot_count', 'unknown')}",
        f"latest_snapshot_name: {summary.get('latest_snapshot_name', 'none')}",
    ]
    return "\n".join(fields)


def _agent_test_step_output(test_result: dict[str, object]) -> dict[str, object]:
    output = TestRunResponse.model_validate(test_result).model_dump()
    if test_result.get("ok") is False or test_result.get("timed_out") is True:
        output["diagnosis"] = diagnose_test_failure(
            stdout=str(test_result.get("stdout") or ""),
            stderr=str(test_result.get("stderr") or ""),
            exit_code=(
                int(test_result["exit_code"])
                if isinstance(test_result.get("exit_code"), int)
                else None
            ),
            timed_out=bool(test_result.get("timed_out")),
            command=[
                str(part)
                for part in test_result.get("command", [])
                if isinstance(part, str)
            ],
            test_id=str(test_result.get("test_id") or ""),
        )
    return output


def _agent_capabilities(settings: BiberSettings) -> dict[str, object]:
    registry = build_model_registry(settings).as_response()
    default_model = str(registry.get("default_model") or settings.default_model)
    return {
        "service": "biber-agent",
        "version": "mvp-v1",
        "default_model": default_model,
        "endpoints": {
            "create_session": "POST /v1/agent/sessions",
            "list_sessions": "GET /v1/agent/sessions",
            "get_session": "GET /v1/agent/sessions/{session_id}",
            "run_test": "POST /v1/tests/run",
            "diagnose_test_failure": "POST /v1/tests/diagnose",
            "edit_file": "POST /v1/files/edit",
            "edit_plan": "POST /v1/files/edit/plan",
            "github_save": "POST /v1/save/github",
            "github_pull_request": "POST /v1/github/pull-request",
        },
        "features": {
            "repo_context": {
                "enabled": True,
                "plan_endpoint": "POST /v1/repo/context/plan",
                "max_files": settings.repo_context_max_files,
                "max_bytes_per_file": settings.repo_context_max_bytes_per_file,
                "max_total_bytes": settings.repo_context_max_total_bytes,
                "planner_supported": True,
                "stack_profiles_supported": True,
                "stack_profiles": list_repo_context_stack_profiles(),
            },
            "workspace_edit": {
                "enabled": True,
                "plan_endpoint": "POST /v1/files/edit/plan",
                "multi_file_plan_supported": True,
                "max_plan_files": 8,
                "dry_run_supported": True,
                "max_file_bytes": settings.workspace_edit_max_file_bytes,
                "max_new_text_bytes": settings.workspace_edit_max_new_text_bytes,
            },
            "test_runner": {
                "enabled": True,
                "diagnosis_endpoint": "POST /v1/tests/diagnose",
                "failure_diagnosis_supported": True,
                "diagnosis_stacks": SUPPORTED_STACKS,
                "commands": list_test_commands(settings),
            },
            "github_workflow": {
                "save_configured": bool(settings.github_token),
                "pull_request_configured": bool(settings.github_token),
            },
            "openai_mentor": {
                "enabled": settings.mentor_enabled,
                "configured": bool(settings.openai_api_key and settings.openai_model),
                "trigger_phrase": MENTOR_TRIGGER_PHRASE,
            },
            "xriq_private_devnet": {
                "context_supported": True,
                "overview_endpoint": "GET /v1/xriq/private-devnet/overview",
                "dashboard_endpoint": "GET /xriq/private-devnet/dashboard",
                "default_explorer_limit": 5,
                "default_snapshot_limit": 5,
                "max_context_limit": 25,
            },
        },
        "presets": [
            {
                "id": "default_coding_session",
                "label": "Default coding session",
                "description": "Repo-aware chat with optional bounded edit and test run.",
                "request_template": {
                    "model": default_model,
                    "task_type": "agent_session",
                    "use_mentor": False,
                    "repo_context_paths": [],
                    "include_xriq_context": False,
                    "test_id": "python-compileall-api",
                },
            },
            {
                "id": "xriq_private_devnet_review",
                "label": "XRIQ private-devnet review",
                "description": (
                    "Rust/XRIQ session that includes current private-devnet "
                    "overview context before chat."
                ),
                "request_template": {
                    "model": default_model,
                    "language": "Rust",
                    "task_type": "xriq_private_devnet_review",
                    "use_mentor": False,
                    "repo_context_paths": [
                        "README.md",
                        "docs/XRIQ_TECHNICAL_SPEC.md",
                        "xriq/README.md",
                    ],
                    "include_xriq_context": True,
                    "xriq_explorer_limit": 5,
                    "xriq_snapshot_limit": 5,
                    "test_id": "python-compileall-api",
                },
            },
        ],
        "safety": {
            "arbitrary_shell_commands": False,
            "bounded_workspace_edits": True,
            "github_actions_explicit_only": True,
            "mentor_calls_disabled_by_default": True,
            "credentials_returned": False,
        },
    }


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


@app.get("/v1/models")
async def models(settings: BiberSettings = Depends(get_settings)) -> dict[str, object]:
    return build_model_registry(settings).as_response()


@app.get("/v1/tests")
async def list_tests(
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    return {"commands": list_test_commands(settings)}


@app.post("/v1/tests/run", response_model=TestRunResponse)
async def run_tests(
    request_body: TestRunRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> TestRunResponse:
    try:
        result = run_test_command(
            request_body.test_id,
            settings,
            dry_run=request_body.dry_run,
        )
    except UnknownTestCommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TestRunnerConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TestRunResponse.model_validate(result)


@app.post("/v1/tests/diagnose", response_model=TestFailureDiagnosisResponse)
async def diagnose_tests(
    request_body: TestFailureDiagnosisRequest,
    _: AuthContext = Depends(require_api_key),
) -> TestFailureDiagnosisResponse:
    result = diagnose_test_failure(
        stdout=request_body.stdout,
        stderr=request_body.stderr,
        exit_code=request_body.exit_code,
        timed_out=request_body.timed_out,
        command=request_body.command,
        test_id=request_body.test_id,
        max_context_lines=request_body.max_context_lines,
    )
    return TestFailureDiagnosisResponse.model_validate(result)


@app.get("/v1/agent/capabilities")
async def agent_capabilities(
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    return _agent_capabilities(settings)


@app.post("/v1/repo/context/plan", response_model=RepoContextPlanResponse)
async def repo_context_plan(
    request_body: RepoContextPlanRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> RepoContextPlanResponse:
    try:
        result = plan_repo_context(
            root=settings.repo_context_root,
            instruction=request_body.instruction,
            pinned_paths=request_body.pinned_paths,
            changed_paths=request_body.changed_paths,
            max_files=min(request_body.max_files, settings.repo_context_max_files),
            max_scan_files=request_body.max_scan_files,
        )
    except RepoContextError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RepoContextPlanResponse.model_validate(result)


@app.post("/v1/files/edit", response_model=WorkspaceEditResponse)
async def edit_workspace_file(
    request_body: WorkspaceEditRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> WorkspaceEditResponse:
    try:
        result = apply_workspace_edit(
            path=request_body.path,
            old_text=request_body.old_text,
            new_text=request_body.new_text,
            expected_replacements=request_body.expected_replacements,
            create_if_missing=request_body.create_if_missing,
            dry_run=request_body.dry_run,
            settings=settings,
        )
    except WorkspaceEditConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkspaceEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceEditResponse.model_validate(result)


@app.post("/v1/files/edit/plan", response_model=WorkspaceEditPlanResponse)
async def plan_workspace_file_edits(
    request_body: WorkspaceEditPlanRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> WorkspaceEditPlanResponse:
    try:
        result = plan_workspace_edits(
            edits=[edit.model_dump() for edit in request_body.edits],
            settings=settings,
            max_files=request_body.max_files,
        )
    except WorkspaceEditConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WorkspaceEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorkspaceEditPlanResponse.model_validate(result)


@app.get("/v1/agent/sessions")
async def get_agent_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    return {"sessions": list_agent_sessions(settings, limit=limit)}


@app.get("/v1/agent/sessions/{session_id}", response_model=AgentSessionResponse)
async def get_agent_session(
    session_id: str,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> AgentSessionResponse:
    try:
        payload = load_agent_session(session_id, settings)
    except AgentSessionStoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AgentSessionResponse.model_validate(payload)


@app.post("/v1/agent/sessions", response_model=AgentSessionResponse)
async def run_agent_session(
    request_body: AgentSessionRequest,
    auth: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> AgentSessionResponse:
    steps: list[AgentSessionStep] = []
    created_at = datetime.now(UTC).isoformat()
    messages = [ChatMessage(role="user", content=request_body.instruction)]

    if request_body.include_xriq_context:
        try:
            xriq_overview = run_private_devnet_overview(
                settings,
                explorer_limit=request_body.xriq_explorer_limit,
                snapshot_limit=request_body.xriq_snapshot_limit,
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
        messages.insert(
            0,
            ChatMessage(role="system", content=_format_xriq_agent_context(xriq_overview)),
        )
        steps.append(
            AgentSessionStep(
                name="xriq_context",
                status="ok",
                output={"overview": xriq_overview},
            )
        )

    chat_request = ChatRequest(
        messages=messages,
        model=request_body.model,
        language=request_body.language,
        task_type=request_body.task_type,
        temperature=request_body.temperature,
        max_tokens=request_body.max_tokens,
        use_mentor=request_body.use_mentor,
        repo_context_paths=request_body.repo_context_paths,
    )

    try:
        content, mentor_notes, _, model_id = await BiberChatService(settings).generate(
            chat_request
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
                "repo_context_files": len(request_body.repo_context_paths),
            },
        )
    )

    if request_body.workspace_edit is not None:
        try:
            edit_result = apply_workspace_edit(
                path=request_body.workspace_edit.path,
                old_text=request_body.workspace_edit.old_text,
                new_text=request_body.workspace_edit.new_text,
                expected_replacements=request_body.workspace_edit.expected_replacements,
                create_if_missing=request_body.workspace_edit.create_if_missing,
                dry_run=request_body.workspace_edit.dry_run,
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

    if request_body.test_id:
        try:
            test_result = run_test_command(
                request_body.test_id,
                settings,
                dry_run=request_body.test_dry_run,
            )
        except UnknownTestCommandError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except TestRunnerConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        steps.append(
            AgentSessionStep(
                name="test_run",
                status="ok" if test_result.get("ok") is not False else "failed",
                output=_agent_test_step_output(test_result),
            )
        )

    github_url = None
    pull_request_url = None
    pull_request_number = None
    github = GitHubClient(settings)
    if request_body.save_to_github is not None:
        try:
            github_url = await github.save_text(request_body.save_to_github, content)
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

    if request_body.pull_request is not None:
        try:
            pr_result = await github.create_pull_request(request_body.pull_request)
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
        priority=auth.priority,
    )
    try:
        artifact = persist_agent_session(response, settings)
    except AgentSessionStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response.artifact_path = str(artifact["artifact_path"])
    return response


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
        content, mentor_notes, raw, model_id = await service.generate(request_body)
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
        model=model_id,
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


@app.post("/v1/github/pull-request", response_model=CreateGitHubPullRequestResponse)
async def create_github_pull_request(
    request_body: CreateGitHubPullRequestRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> CreateGitHubPullRequestResponse:
    try:
        result = await GitHubClient(settings).create_pull_request(request_body)
    except GitHubDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GitHubConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubPullRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CreateGitHubPullRequestResponse.model_validate(result)


@app.post("/v1/xriq/private-devnet/preflight-transfer")
async def xriq_private_devnet_preflight_transfer(
    request_body: XriqPreflightTransferRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return run_private_devnet_preflight_transfer(request_body, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/overview")
async def xriq_private_devnet_overview(
    explorer_limit: int = Query(default=5, ge=1, le=100),
    snapshot_limit: int = Query(default=5, ge=1, le=100),
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
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
async def xriq_private_devnet_status(
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
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
async def xriq_private_devnet_explorer_overview(
    limit: int | None = Query(default=None, ge=1, le=100),
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
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
async def xriq_private_devnet_block_detail(
    height: int = ApiPath(ge=0),
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
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
async def xriq_private_devnet_account_detail(
    address: str,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
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
async def xriq_private_devnet_transaction_detail(
    tx_hash: str,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
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
async def xriq_private_devnet_mempool_detail(
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
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
async def xriq_private_devnet_snapshot_export(
    request_body: XriqSnapshotExportRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return run_private_devnet_snapshot_export(request_body, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.post("/v1/xriq/private-devnet/snapshots/import")
async def xriq_private_devnet_snapshot_import(
    request_body: XriqSnapshotImportRequest,
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return run_private_devnet_snapshot_import(request_body, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqCommandTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except XriqCommandError as exc:
        detail: object = exc.payload or str(exc)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


@app.get("/v1/xriq/private-devnet/snapshots")
async def xriq_private_devnet_snapshots(
    limit: int = Query(default=20, ge=1, le=100),
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return list_private_devnet_snapshots(settings, limit=limit)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqSnapshotStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/v1/xriq/private-devnet/snapshots/{snapshot_name}")
async def xriq_private_devnet_snapshot_detail(
    snapshot_name: str = ApiPath(pattern=SNAPSHOT_NAME_PATTERN),
    _: AuthContext = Depends(require_api_key),
    settings: BiberSettings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return get_private_devnet_snapshot(snapshot_name, settings)
    except XriqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except XriqSnapshotStoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


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

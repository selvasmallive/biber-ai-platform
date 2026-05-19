from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class GitHubSaveTarget(BaseModel):
    path: str = Field(min_length=1, description="Repository path to create or update.")
    owner: str | None = None
    repo: str | None = None
    branch: str = "main"
    base_branch: str | None = None
    create_branch_if_missing: bool = False
    commit_message: str = "Save BIBER generated code"


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None
    language: str | None = None
    task_type: str = "code_generation"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0, le=32000)
    use_mentor: bool = True
    repo_context_paths: list[str] = Field(default_factory=list, max_length=12)
    save_to_github: GitHubSaveTarget | None = None
    backup_to_azure: bool = False


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


class SaveToGitHubRequest(BaseModel):
    target: GitHubSaveTarget
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


class RuntimeStatus(BaseModel):
    service: str
    local_model_name: str
    local_model_base_url: str
    mentor_enabled: bool
    mentor_configured: bool
    mentor_trigger_phrase: str
    github_configured: bool
    azure_backup_configured: bool


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


class TestFailureDiagnosisRequest(BaseModel):
    test_id: str | None = None
    command: list[str] = Field(default_factory=list, max_length=20)
    exit_code: int | None = None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    max_context_lines: int = Field(default=80, ge=1, le=200)


class TestFailureSignal(BaseModel):
    category: str
    stack: str
    message: str
    line_number: int | None = None
    evidence: str


class TestFailureDiagnosisResponse(BaseModel):
    has_failure: bool
    primary_category: str
    detected_stack: str
    signals: list[TestFailureSignal]
    relevant_output: str
    suggested_next_actions: list[str]
    summary: str


class RepoContextPlanRequest(BaseModel):
    instruction: str | None = None
    pinned_paths: list[str] = Field(default_factory=list, max_length=12)
    changed_paths: list[str] = Field(default_factory=list, max_length=50)
    max_files: int = Field(default=12, ge=1, le=50)
    max_scan_files: int = Field(default=2000, ge=1, le=10000)


class RepoContextCandidate(BaseModel):
    path: str
    reason: str
    project_type: str | None = None
    priority: int


class RepoContextPlanResponse(BaseModel):
    selected_paths: list[str]
    detected_project_types: list[str]
    candidates: list[RepoContextCandidate]
    skipped: list[dict[str, str]]
    summary: str


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


class WorkspaceEditPlanRequest(BaseModel):
    edits: list[WorkspaceEditRequest] = Field(min_length=1, max_length=20)
    max_files: int = Field(default=8, ge=1, le=20)


class WorkspaceEditPlanItem(BaseModel):
    path: str
    operation: str
    changed: bool
    replacements: int
    old_sha256: str | None
    new_sha256: str
    old_bytes: int
    new_bytes: int
    risk_level: str
    notes: list[str]


class WorkspaceEditPlanRejection(BaseModel):
    path: str
    error: str


class WorkspaceEditPlanResponse(BaseModel):
    ok: bool
    planned: list[WorkspaceEditPlanItem]
    rejected: list[WorkspaceEditPlanRejection]
    files_touched: int
    total_new_bytes: int
    summary: str


class AgentSessionRequest(BaseModel):
    instruction: str = Field(min_length=1)
    model: str | None = None
    language: str | None = None
    task_type: str = "agent_session"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=512, gt=0, le=32000)
    use_mentor: bool = False
    repo_context_paths: list[str] = Field(default_factory=list, max_length=12)
    include_xriq_context: bool = False
    xriq_explorer_limit: int = Field(default=5, ge=1, le=25)
    xriq_snapshot_limit: int = Field(default=5, ge=1, le=25)
    workspace_edit: WorkspaceEditRequest | None = None
    test_id: str | None = "python-compileall-api"
    test_dry_run: bool = False
    save_to_github: GitHubSaveTarget | None = None
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

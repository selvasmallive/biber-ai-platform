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

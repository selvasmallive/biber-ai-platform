from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings
from biber_api.llm import BiberChatService, ModelResult
from biber_api.repo_context import (
    RepoContextError,
    build_repo_context_message,
    plan_repo_context,
)
from biber_api.schemas import ChatMessage, ChatRequest


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int | None,
    ) -> ModelResult:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return ModelResult(content="local answer", raw={})


def settings(root: Path) -> BiberSettings:
    return BiberSettings(
        env="test",
        api_keys=("test-key",),
        priority_passcodes={},
        local_model_base_url="http://local-model/v1",
        local_model_name="biber-dev-core",
        local_model_timeout_seconds=1,
        mentor_enabled=False,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key=None,
        openai_model=None,
        github_token=None,
        github_default_owner=None,
        github_default_repo=None,
        azure_storage_connection_string=None,
        azure_blob_container="biber-backups",
        repo_context_root=str(root),
        repo_context_max_files=4,
        repo_context_max_bytes_per_file=80,
        repo_context_max_total_bytes=200,
    )


def test_build_repo_context_message_includes_selected_files(tmp_path: Path) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def hello() -> str:\n    return 'hello'\n", encoding="utf-8")

    context = build_repo_context_message(
        ["src/service.py"],
        root=str(tmp_path),
        max_files=4,
        max_bytes_per_file=200,
        max_total_bytes=500,
    )

    assert context is not None
    assert "Repository context from selected files" in context
    assert "--- FILE: src/service.py" in context
    assert "def hello" in context


def test_repo_context_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(RepoContextError, match="escapes"):
        build_repo_context_message(
            ["../secret.txt"],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_rejects_absolute_paths(tmp_path: Path) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def hello() -> str:\n    return 'hello'\n", encoding="utf-8")

    with pytest.raises(RepoContextError, match="workspace-relative"):
        build_repo_context_message(
            [str(source)],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_rejects_secret_like_paths(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")

    with pytest.raises(RepoContextError, match="not allowed"):
        build_repo_context_message(
            [".env"],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_rejects_denied_paths_case_insensitively(tmp_path: Path) -> None:
    source = tmp_path / "Node_Modules" / "package" / "index.js"
    source.parent.mkdir(parents=True)
    source.write_text("console.log('skip me')\n", encoding="utf-8")

    with pytest.raises(RepoContextError, match="not allowed"):
        build_repo_context_message(
            ["Node_Modules/package/index.js"],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_truncates_large_files(tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    source.write_text("abcdefghij" * 20, encoding="utf-8")

    context = build_repo_context_message(
        ["large.txt"],
        root=str(tmp_path),
        max_files=4,
        max_bytes_per_file=25,
        max_total_bytes=25,
    )

    assert context is not None
    assert "truncated" in context
    assert "abcdefghijabcdefghijabcde" in context


def test_plan_repo_context_selects_dotnet_changed_file_and_related_test(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("# Example\n", encoding="utf-8")
    (tmp_path / "Example.sln").write_text("solution\n", encoding="utf-8")
    project = tmp_path / "src" / "Example.Api" / "Example.Api.csproj"
    project.parent.mkdir(parents=True)
    project.write_text("<Project />\n", encoding="utf-8")
    source = project.parent / "Controllers" / "WeatherController.cs"
    source.parent.mkdir()
    source.write_text("public sealed class WeatherController {}\n", encoding="utf-8")
    test = tmp_path / "tests" / "Example.Api.Tests" / "WeatherControllerTests.cs"
    test.parent.mkdir(parents=True)
    test.write_text("public sealed class WeatherControllerTests {}\n", encoding="utf-8")
    secret = tmp_path / ".env"
    secret.write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    generated = tmp_path / "bin" / "Debug" / "ignored.dll"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"binary")

    plan = plan_repo_context(
        root=str(tmp_path),
        instruction="Fix the WeatherController forecast route.",
        changed_paths=["src/Example.Api/Controllers/WeatherController.cs"],
        max_files=8,
    )

    assert "dotnet" in plan["detected_project_types"]
    selected = plan["selected_paths"]
    assert "src/Example.Api/Controllers/WeatherController.cs" in selected
    assert "tests/Example.Api.Tests/WeatherControllerTests.cs" in selected
    assert "Example.sln" in selected
    assert "src/Example.Api/Example.Api.csproj" in selected
    assert ".env" not in selected
    assert "bin/Debug/ignored.dll" not in selected
    profiles = {profile["id"]: profile for profile in plan["stack_profiles"]}
    assert profiles["dotnet"]["recommended_test_ids"] == ["dotnet-test"]
    assert "Program.cs" in profiles["dotnet"]["entrypoint_patterns"]


def test_plan_repo_context_selects_java_entrypoint_and_profile(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("# Java Example\n", encoding="utf-8")
    (tmp_path / "pom.xml").write_text("<project />\n", encoding="utf-8")
    application = (
        tmp_path
        / "src"
        / "main"
        / "java"
        / "com"
        / "example"
        / "BillingApplication.java"
    )
    application.parent.mkdir(parents=True)
    application.write_text("class BillingApplication {}\n", encoding="utf-8")
    service = application.parent / "BillingService.java"
    service.write_text("class BillingService {}\n", encoding="utf-8")
    test = tmp_path / "src" / "test" / "java" / "com" / "example" / "BillingServiceTest.java"
    test.parent.mkdir(parents=True)
    test.write_text("class BillingServiceTest {}\n", encoding="utf-8")

    plan = plan_repo_context(
        root=str(tmp_path),
        instruction="Fix BillingService invoice total logic.",
        changed_paths=["src/main/java/com/example/BillingService.java"],
        max_files=8,
    )

    assert "java" in plan["detected_project_types"]
    selected = plan["selected_paths"]
    assert "src/main/java/com/example/BillingService.java" in selected
    assert "src/test/java/com/example/BillingServiceTest.java" in selected
    assert "pom.xml" in selected
    assert "src/main/java/com/example/BillingApplication.java" in selected
    profiles = {profile["id"]: profile for profile in plan["stack_profiles"]}
    assert profiles["java"]["recommended_test_ids"] == [
        "maven-test",
        "gradle-test",
        "gradle-wrapper-test",
    ]
    assert "*Application.java" in profiles["java"]["entrypoint_patterns"]


def test_plan_repo_context_rejects_secret_pinned_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")

    with pytest.raises(RepoContextError, match="not allowed"):
        plan_repo_context(root=str(tmp_path), pinned_paths=[".env"])


def test_repo_context_plan_endpoint_returns_selected_paths(tmp_path: Path) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def hello() -> str:\n    return 'hello'\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    test = tmp_path / "tests" / "test_service.py"
    test.parent.mkdir()
    test.write_text("def test_hello():\n    assert True\n", encoding="utf-8")

    app_settings = settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: app_settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/repo/context/plan",
            headers={"x-api-key": "test-key"},
            json={
                "instruction": "Fix service hello behavior",
                "changed_paths": ["src/service.py"],
                "max_files": 4,
            },
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["selected_paths"][0] == "src/service.py"
    assert "python" in body["detected_project_types"]
    assert "tests/test_service.py" in body["selected_paths"]
    assert body["stack_profiles"] == []
    assert body["summary"].startswith("Detected")


def test_chat_service_injects_repo_context_into_local_prompt(tmp_path: Path) -> None:
    source = tmp_path / "xriq" / "wallet.rs"
    source.parent.mkdir()
    source.write_text("pub fn sign() {}\n", encoding="utf-8")
    service = BiberChatService(settings(tmp_path))
    local = FakeClient()
    service._local = local

    content, mentor_notes, _, model_id = asyncio.run(
        service.generate(
            ChatRequest(
                messages=[ChatMessage(role="user", content="Explain this file.")],
                language="Rust",
                repo_context_paths=["xriq/wallet.rs"],
            )
        )
    )

    system_prompt = local.calls[0]["messages"][0]["content"]
    assert content == "local answer"
    assert mentor_notes is None
    assert model_id == "biber-dev-core-v1"
    assert "--- FILE: xriq/wallet.rs" in system_prompt
    assert "pub fn sign" in system_prompt

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest

from biber_api.config import BiberSettings
from biber_api.github import (
    GitHubClient,
    GitHubConfigurationError,
    GitHubDisabled,
    GitHubSaveError,
)
from biber_api.schemas import GitHubSaveTarget


def make_settings(
    *,
    github_token: str | None = "ghp_test",
    github_default_owner: str | None = "acme",
    github_default_repo: str | None = "biber-generated",
) -> BiberSettings:
    return BiberSettings(
        env="test",
        api_keys=("test-key",),
        priority_passcodes={},
        local_model_base_url="http://127.0.0.1:8001/v1",
        local_model_name="biber-dev-core",
        local_model_timeout_seconds=10,
        mentor_enabled=False,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key=None,
        openai_model=None,
        github_token=github_token,
        github_default_owner=github_default_owner,
        github_default_repo=github_default_repo,
        azure_storage_connection_string=None,
        azure_blob_container="biber-backups",
    )


def test_save_text_requires_github_token() -> None:
    client = GitHubClient(make_settings(github_token=None))
    target = GitHubSaveTarget(path="generated/example.py")

    with pytest.raises(GitHubDisabled, match="not configured"):
        asyncio.run(client.save_text(target, "print('hello')\n"))


def test_save_text_requires_owner_and_repo() -> None:
    client = GitHubClient(
        make_settings(github_default_owner=None, github_default_repo=None)
    )
    target = GitHubSaveTarget(path="generated/example.py")

    with pytest.raises(GitHubConfigurationError, match="owner and repo"):
        asyncio.run(client.save_text(target, "print('hello')\n"))


def test_save_text_creates_new_file() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(404, request=request)
        assert request.method == "PUT"
        body = json.loads(request.content)
        assert body["message"] == "Save BIBER generated code"
        assert body["branch"] == "main"
        assert body["content"] == base64.b64encode(b"print('hello')\n").decode("ascii")
        assert "sha" not in body
        return httpx.Response(
            201,
            json={
                "content": {
                    "html_url": (
                        "https://github.com/acme/biber-generated/blob/main/"
                        "generated/example.py"
                    )
                }
            },
            request=request,
        )

    client = GitHubClient(make_settings(), transport=httpx.MockTransport(handler))
    target = GitHubSaveTarget(path="/generated/example.py")

    url = asyncio.run(client.save_text(target, "print('hello')\n"))

    assert url == "https://github.com/acme/biber-generated/blob/main/generated/example.py"
    assert [request.method for request in requests] == ["GET", "PUT"]
    assert requests[0].url.params["ref"] == "main"


def test_save_text_updates_existing_file_with_sha() -> None:
    put_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"sha": "abc123"}, request=request)
        assert request.method == "PUT"
        put_body.update(json.loads(request.content))
        return httpx.Response(200, json={"content": {}}, request=request)

    client = GitHubClient(make_settings(), transport=httpx.MockTransport(handler))
    target = GitHubSaveTarget(path="generated/example.py", branch="dev")

    url = asyncio.run(client.save_text(target, "print('hello')\n"))

    assert put_body["sha"] == "abc123"
    assert put_body["branch"] == "dev"
    assert url == "https://api.github.com/repos/acme/biber-generated/contents/generated/example.py"


def test_save_text_wraps_github_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"message": "Resource not accessible"},
            request=request,
        )

    client = GitHubClient(make_settings(), transport=httpx.MockTransport(handler))
    target = GitHubSaveTarget(path="generated/example.py")

    with pytest.raises(GitHubSaveError, match="403: Resource not accessible"):
        asyncio.run(client.save_text(target, "print('hello')\n"))

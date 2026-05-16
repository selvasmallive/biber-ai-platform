from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx

from app.config import settings


class GitHubDisabled(RuntimeError):
    pass


class GitHubConfigurationError(ValueError):
    pass


class GitHubSaveError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubSaveTarget:
    path: str
    owner: str | None = None
    repo: str | None = None
    branch: str = "main"
    commit_message: str = "Save BIBER generated code"


class GitHubClient:
    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(settings.github_token)

    async def save_text(self, target: GitHubSaveTarget, content: str) -> str:
        if not self.enabled:
            raise GitHubDisabled("GitHub saving is not configured.")

        owner = target.owner or settings.github_default_owner
        repo = target.repo or settings.github_default_repo
        if not owner or not repo:
            raise GitHubConfigurationError("GitHub owner and repo are required.")

        path = _normalized_path(target.path)

        headers = {
            "accept": "application/vnd.github+json",
            "authorization": f"Bearer {settings.github_token}",
            "x-github-api-version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": target.branch}
        body = {
            "message": target.commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": target.branch,
        }
        client_kwargs: dict[str, object] = {"timeout": self._timeout_seconds}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                existing = await client.get(url, headers=headers, params=params)
                if existing.status_code == 200:
                    body["sha"] = existing.json().get("sha")
                elif existing.status_code not in {404, 409}:
                    existing.raise_for_status()

                response = await client.put(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                return data.get("content", {}).get("html_url", url)
        except httpx.HTTPStatusError as exc:
            raise GitHubSaveError(_github_status_detail(exc.response)) from exc
        except httpx.HTTPError as exc:
            raise GitHubSaveError(f"GitHub API request failed: {exc}") from exc


def _normalized_path(path: str) -> str:
    normalized = path.strip().lstrip("/")
    if not normalized:
        raise GitHubConfigurationError("GitHub target path is required.")
    if normalized == ".." or normalized.startswith("../") or "/../" in normalized:
        raise GitHubConfigurationError("GitHub target path cannot contain '..' segments.")
    return normalized


def _github_status_detail(response: httpx.Response) -> str:
    detail = ""
    try:
        data = response.json()
        if isinstance(data, dict):
            detail = str(data.get("message") or "")
    except ValueError:
        detail = response.text.strip()
    suffix = f": {detail[:200]}" if detail else ""
    return f"GitHub API returned {response.status_code}{suffix}."

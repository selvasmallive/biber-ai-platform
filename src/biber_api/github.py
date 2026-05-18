from __future__ import annotations

import base64
import re

import httpx

from .config import BiberSettings
from .schemas import CreateGitHubPullRequestRequest, GitHubSaveTarget


class GitHubDisabled(RuntimeError):
    pass


class GitHubConfigurationError(ValueError):
    pass


class GitHubSaveError(RuntimeError):
    pass


class GitHubPullRequestError(RuntimeError):
    pass


class GitHubClient:
    def __init__(
        self,
        settings: BiberSettings,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return bool(self._settings.github_token)

    async def save_text(self, target: GitHubSaveTarget, content: str) -> str:
        if not self.enabled:
            raise GitHubDisabled("GitHub saving is not configured.")

        owner = target.owner or self._settings.github_default_owner
        repo = target.repo or self._settings.github_default_repo
        if not owner or not repo:
            raise GitHubConfigurationError("GitHub owner and repo are required.")

        path = _normalized_path(target.path)
        branch = _normalized_branch(target.branch, "GitHub target branch")
        base_branch = _normalized_branch(
            target.base_branch or branch,
            "GitHub base branch",
        )

        headers = {
            "accept": "application/vnd.github+json",
            "authorization": f"Bearer {self._settings.github_token}",
            "x-github-api-version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": branch}
        body = {
            "message": target.commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        client_kwargs: dict[str, object] = {"timeout": self._timeout_seconds}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                if target.create_branch_if_missing:
                    await _ensure_branch(
                        client,
                        headers=headers,
                        owner=owner,
                        repo=repo,
                        branch=branch,
                        base_branch=base_branch,
                    )

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

    async def create_pull_request(
        self,
        target: CreateGitHubPullRequestRequest,
    ) -> dict[str, object]:
        if not self.enabled:
            raise GitHubDisabled("GitHub saving is not configured.")

        owner = target.owner or self._settings.github_default_owner
        repo = target.repo or self._settings.github_default_repo
        if not owner or not repo:
            raise GitHubConfigurationError("GitHub owner and repo are required.")

        head = _normalized_branch(target.head, "GitHub PR head branch")
        base = _normalized_branch(target.base, "GitHub PR base branch")
        if not target.title.strip():
            raise GitHubConfigurationError("GitHub PR title is required.")

        headers = {
            "accept": "application/vnd.github+json",
            "authorization": f"Bearer {self._settings.github_token}",
            "x-github-api-version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        body = {
            "title": target.title,
            "head": head,
            "base": base,
            "body": target.body,
            "draft": target.draft,
        }
        client_kwargs: dict[str, object] = {"timeout": self._timeout_seconds}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                return {
                    "url": data.get("html_url", url),
                    "number": data.get("number"),
                }
        except httpx.HTTPStatusError as exc:
            raise GitHubPullRequestError(_github_status_detail(exc.response)) from exc
        except httpx.HTTPError as exc:
            raise GitHubPullRequestError(f"GitHub API request failed: {exc}") from exc


def _normalized_path(path: str) -> str:
    normalized = path.strip().lstrip("/")
    if not normalized:
        raise GitHubConfigurationError("GitHub target path is required.")
    if normalized == ".." or normalized.startswith("../") or "/../" in normalized:
        raise GitHubConfigurationError("GitHub target path cannot contain '..' segments.")
    return normalized


_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._/-]*[A-Za-z0-9])?$")


def _normalized_branch(branch: str, label: str) -> str:
    normalized = branch.strip()
    if not normalized:
        raise GitHubConfigurationError(f"{label} is required.")
    if (
        normalized.startswith("refs/")
        or normalized.startswith("/")
        or normalized.endswith("/")
        or ".." in normalized
        or "@{" in normalized
        or "\\" in normalized
        or not _BRANCH_PATTERN.fullmatch(normalized)
    ):
        raise GitHubConfigurationError(f"{label} is not allowed.")
    return normalized


async def _ensure_branch(
    client: httpx.AsyncClient,
    *,
    headers: dict[str, str],
    owner: str,
    repo: str,
    branch: str,
    base_branch: str,
) -> None:
    branch_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}"
    existing = await client.get(branch_url, headers=headers)
    if existing.status_code == 200:
        return
    if existing.status_code != 404:
        existing.raise_for_status()
    if branch == base_branch:
        raise GitHubConfigurationError(
            "GitHub branch does not exist and cannot be created from itself."
        )

    base_url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{base_branch}"
    base = await client.get(base_url, headers=headers)
    base.raise_for_status()
    base_sha = base.json().get("object", {}).get("sha")
    if not base_sha:
        raise GitHubConfigurationError("GitHub base branch response did not include a SHA.")

    create = await client.post(
        f"https://api.github.com/repos/{owner}/{repo}/git/refs",
        headers=headers,
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )
    if create.status_code not in {201, 422}:
        create.raise_for_status()
    if create.status_code == 422:
        retry = await client.get(branch_url, headers=headers)
        retry.raise_for_status()


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

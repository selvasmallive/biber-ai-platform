from __future__ import annotations

import base64

import httpx

from .config import BiberSettings
from .schemas import GitHubSaveTarget


class GitHubDisabled(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, settings: BiberSettings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self._settings.github_token)

    async def save_text(self, target: GitHubSaveTarget, content: str) -> str:
        if not self.enabled:
            raise GitHubDisabled("GitHub saving is not configured.")

        owner = target.owner or self._settings.github_default_owner
        repo = target.repo or self._settings.github_default_repo
        if not owner or not repo:
            raise ValueError("GitHub owner and repo are required.")

        headers = {
            "accept": "application/vnd.github+json",
            "authorization": f"Bearer {self._settings.github_token}",
            "x-github-api-version": "2022-11-28",
        }
        path = target.path.lstrip("/")
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        params = {"ref": target.branch}
        body = {
            "message": target.commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": target.branch,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            existing = await client.get(url, headers=headers, params=params)
            if existing.status_code == 200:
                body["sha"] = existing.json().get("sha")
            elif existing.status_code not in {404, 409}:
                existing.raise_for_status()

            response = await client.put(url, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            return data.get("content", {}).get("html_url", url)

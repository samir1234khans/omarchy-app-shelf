"""Read-only GitHub repository, Pages and deployment discovery."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from ..constants import GITHUB_API_VERSION
from ..errors import AppShelfError, ProviderError
from ..security import validate_url_syntax
from .base import ProviderContext, normalized_record

_LINK_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


class GitHubProvider:
    name = "github"
    api_root = "https://api.github.com"

    def __init__(self, context: ProviderContext):
        self.context = context
        self.settings = context.settings
        token = context.secrets.get(self.name)
        if not token:
            raise AppShelfError(
                "credential_missing",
                "GitHub is enabled but no GitHub access token is stored.",
                details={"provider": self.name},
            )
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }

    def _get_url(self, url: str) -> tuple[Any, dict[str, str]]:
        return self.context.client.get_json(
            url,
            headers=self.headers,
            provider=self.name,
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{self.api_root}{path}" + (f"?{query}" if query else "")
        return self._get_url(url)

    def _repositories(self) -> list[dict]:
        limit = max(1, min(int(self.settings.get("maxRepositories", 250)), 1000))
        url = (
            f"{self.api_root}/user/repos?"
            + urllib.parse.urlencode(
                {
                    "per_page": 100,
                    "sort": "updated",
                    "direction": "desc",
                    "affiliation": "owner,collaborator,organization_member",
                }
            )
        )
        repositories: list[dict] = []
        for _ in range(10):
            payload, headers = self._get_url(url)
            batch = payload if isinstance(payload, list) else []
            repositories.extend(item for item in batch if isinstance(item, dict))
            if len(repositories) >= limit:
                return repositories[:limit]
            match = _LINK_NEXT.search(headers.get("link", ""))
            if not match or not batch:
                break
            url = match.group(1)
        return repositories[:limit]

    @staticmethod
    def _https(value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            normalized = validate_url_syntax(raw)
        except Exception:
            return ""
        return normalized if normalized.startswith("https://") else ""

    def _pages_url(self, owner: str, repo: str) -> str:
        try:
            payload, _ = self._get(
                f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/pages"
            )
        except ProviderError as exc:
            if isinstance(exc.details, dict) and exc.details.get("status") in {403, 404}:
                return ""
            return ""
        return self._https(payload.get("html_url", "")) if isinstance(payload, dict) else ""

    def _deployment_url(self, owner: str, repo: str) -> str:
        try:
            deployments, _ = self._get(
                f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/deployments",
                {"environment": "production", "per_page": 10},
            )
        except ProviderError:
            return ""
        if not isinstance(deployments, list):
            return ""
        ordered = sorted(
            [item for item in deployments if isinstance(item, dict)],
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )
        for deployment in ordered:
            deployment_id = deployment.get("id")
            if deployment_id is None:
                continue
            try:
                statuses, _ = self._get(
                    f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/deployments/{deployment_id}/statuses",
                    {"per_page": 20},
                )
            except ProviderError:
                continue
            if not isinstance(statuses, list):
                continue
            for status in sorted(
                [item for item in statuses if isinstance(item, dict)],
                key=lambda item: str(item.get("created_at") or ""),
                reverse=True,
            ):
                if status.get("state") != "success":
                    continue
                value = self._https(
                    str(status.get("environment_url") or status.get("target_url") or "")
                )
                if value:
                    return value
        return ""

    def discover(self) -> list[dict[str, Any]]:
        excluded = {
            str(value).lower()
            for value in self.settings.get("excludeRepositories", [])
        }
        organizations = {
            str(value).lower()
            for value in self.settings.get("includeOrganizations", [])
        }
        include_forks = bool(self.settings.get("includeForks", False))
        include_archived = bool(self.settings.get("includeArchived", False))
        records: list[dict[str, Any]] = []

        for repository in self._repositories():
            full_name = str(repository.get("full_name") or "")
            if not full_name or full_name.lower() in excluded:
                continue
            owner_data = repository.get("owner") if isinstance(repository.get("owner"), dict) else {}
            owner = str(owner_data.get("login") or full_name.split("/", 1)[0])
            name = str(repository.get("name") or full_name.split("/", 1)[-1])
            if organizations and owner.lower() not in organizations:
                continue
            if repository.get("fork") and not include_forks:
                continue
            if repository.get("archived") and not include_archived:
                continue

            url = self._https(str(repository.get("homepage") or ""))
            source = "homepage" if url else ""
            if not url and repository.get("has_pages"):
                url = self._pages_url(owner, name)
                source = "pages" if url else ""
            if not url:
                url = self._deployment_url(owner, name)
                source = "deployment" if url else ""

            records.append(
                normalized_record(
                    provider=self.name,
                    remote_id=str(repository.get("id")),
                    name=name,
                    url=url,
                    source_repo=full_name,
                    updated_at=repository.get("pushed_at") or repository.get("updated_at"),
                    status="active" if url else "unresolved",
                    metadata={
                        "fullName": full_name,
                        "private": bool(repository.get("private")),
                        "archived": bool(repository.get("archived")),
                        "fork": bool(repository.get("fork")),
                        "htmlUrl": repository.get("html_url"),
                        "urlSource": source,
                    },
                )
            )
        return records

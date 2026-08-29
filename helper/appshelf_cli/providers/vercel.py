"""Read-only Vercel discovery."""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..errors import AppShelfError, ProviderError
from ..security import validate_url_syntax
from ..util import utc_now
from .base import ProviderContext, normalized_record


class VercelProvider:
    name = "vercel"
    api_root = "https://api.vercel.com"

    def __init__(self, context: ProviderContext):
        self.context = context
        self.settings = context.settings
        token = context.secrets.get(self.name)
        if not token:
            raise AppShelfError(
                "credential_missing",
                "Vercel is enabled but no Vercel access token is stored.",
                details={"provider": self.name},
            )
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        self.team_id = str(self.settings.get("teamId") or "")

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        query = dict(params or {})
        if self.team_id:
            query["teamId"] = self.team_id
        suffix = urllib.parse.urlencode(
            {key: value for key, value in query.items() if value not in (None, "")},
            doseq=True,
        )
        return f"{self.api_root}{path}" + (f"?{suffix}" if suffix else "")

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        body, _ = self.context.client.get_json(
            self._url(path, params),
            headers=self.headers,
            provider=self.name,
        )
        return body

    def _list_projects(self) -> list[dict]:
        projects: list[dict] = []
        until: str | int | None = None
        for _ in range(50):
            params: dict[str, Any] = {"limit": 100}
            if until is not None:
                params["until"] = until
            payload = self._get("/v9/projects", params)
            batch = payload.get("projects", []) if isinstance(payload, dict) else []
            projects.extend(item for item in batch if isinstance(item, dict))
            pagination = payload.get("pagination", {}) if isinstance(payload, dict) else {}
            next_value = pagination.get("next") if isinstance(pagination, dict) else None
            if next_value in (None, "", until) or not batch:
                break
            until = next_value
        return projects

    def _domains(self, project_id: str) -> list[dict]:
        try:
            payload = self._get(
                f"/v9/projects/{urllib.parse.quote(project_id, safe='')}/domains",
                {"limit": 100},
            )
        except ProviderError:
            return []
        values = payload.get("domains", []) if isinstance(payload, dict) else []
        return [item for item in values if isinstance(item, dict)]

    def _deployments(self, project_id: str) -> list[dict]:
        try:
            payload = self._get(
                "/v6/deployments",
                {
                    "projectId": project_id,
                    "target": "production",
                    "state": "READY",
                    "limit": 20,
                },
            )
        except ProviderError:
            return []
        values = payload.get("deployments", []) if isinstance(payload, dict) else []
        return [item for item in values if isinstance(item, dict)]

    @staticmethod
    def _repo(project: dict) -> str:
        link = project.get("link")
        if not isinstance(link, dict):
            return ""
        repo = str(link.get("repo") or link.get("repoName") or "").strip("/")
        org = str(link.get("org") or link.get("repoOwner") or "").strip("/")
        if "/" in repo:
            return repo.lower()
        return f"{org}/{repo}".lower() if org and repo else ""

    @staticmethod
    def _https(value: str) -> str:
        candidate = str(value or "").strip()
        if not candidate:
            return ""
        if "://" not in candidate:
            candidate = "https://" + candidate
        try:
            normalized = validate_url_syntax(candidate)
        except Exception:
            return ""
        return normalized if normalized.startswith("https://") else ""

    def _canonical_url(
        self,
        project: dict,
        domains: list[dict],
        deployments: list[dict],
    ) -> str:
        names = [
            str(item.get("name") or "")
            for item in domains
            if item.get("name")
            and item.get("redirect") in (None, "")
            and item.get("verified", True) is not False
        ]
        custom = [name for name in names if not name.endswith(".vercel.app")]
        for name in custom + names:
            resolved = self._https(name)
            if resolved:
                return resolved

        targets = project.get("targets")
        production = targets.get("production") if isinstance(targets, dict) else None
        aliases = production.get("alias", []) if isinstance(production, dict) else []
        if isinstance(aliases, str):
            aliases = [aliases]
        for alias in aliases or []:
            resolved = self._https(str(alias))
            if resolved:
                return resolved

        project_name = str(project.get("name") or "")
        if project_name:
            resolved = self._https(f"{project_name}.vercel.app")
            if resolved:
                return resolved

        for deployment in deployments:
            aliases = deployment.get("alias") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            for alias in aliases:
                resolved = self._https(str(alias))
                if resolved:
                    return resolved
            resolved = self._https(str(deployment.get("url") or ""))
            if resolved:
                return resolved
        return ""

    def discover(self) -> list[dict[str, Any]]:
        included = {str(value) for value in self.settings.get("includeProjects", [])}
        excluded = {str(value) for value in self.settings.get("excludeProjects", [])}
        records: list[dict[str, Any]] = []
        for project in self._list_projects():
            project_id = str(project.get("id") or "")
            name = str(project.get("name") or project_id)
            if not project_id:
                continue
            if included and project_id not in included and name not in included:
                continue
            if project_id in excluded or name in excluded:
                continue
            domains = self._domains(project_id)
            deployments = self._deployments(project_id)
            url = self._canonical_url(project, domains, deployments)
            records.append(
                normalized_record(
                    provider=self.name,
                    remote_id=project_id,
                    name=name,
                    url=url,
                    source_repo=self._repo(project),
                    updated_at=project.get("updatedAt") or project.get("createdAt"),
                    status="active" if url else "unresolved",
                    metadata={
                        "teamId": self.team_id,
                        "framework": project.get("framework"),
                        "accountId": project.get("accountId"),
                        "discoveredAt": utc_now(),
                    },
                )
            )
        return records

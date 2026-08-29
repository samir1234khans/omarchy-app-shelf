"""Provider contracts and normalized records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..http import HttpClient
from ..secrets import SecretStore


@dataclass
class ProviderContext:
    settings: dict[str, Any]
    secrets: SecretStore
    client: HttpClient


class Provider(Protocol):
    name: str

    def discover(self) -> list[dict[str, Any]]:
        ...


def normalized_record(
    *,
    provider: str,
    remote_id: str,
    name: str,
    url: str,
    source_repo: str = "",
    updated_at: str | int | None = None,
    status: str = "active",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "remoteId": str(remote_id),
        "name": str(name or remote_id),
        "url": str(url or ""),
        "sourceRepo": str(source_repo or "").lower(),
        "updatedAt": updated_at,
        "status": status,
        "metadata": metadata or {},
    }

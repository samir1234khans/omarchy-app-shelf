"""Shared runtime construction."""

from __future__ import annotations

from .http import HttpClient


def http_client_from_settings(settings: dict) -> HttpClient:
    security = settings.get("security", {}) if isinstance(settings, dict) else {}
    return HttpClient(
        allow_private=bool(security.get("allowPrivateNetwork", False)),
        allow_http=False,
        allow_local_http=bool(security.get("allowLocalHttp", False)),
    )

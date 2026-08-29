"""UI-facing snapshot assembly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .desktop import desktop_id_for, effective_icon, effective_name, effective_url
from .paths import Paths
from .secrets import SecretStore
from .storage import Store
from .util import file_url


def _pending_plan(store: Store, plan_id: str | None) -> dict | None:
    if not plan_id:
        return None
    candidate = store.paths.state_dir / "sync-plans" / f"{plan_id}.json"
    if not candidate.is_file():
        return None
    try:
        import json

        value = json.loads(candidate.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def build_snapshot(store: Store, secrets: SecretStore | None = None) -> dict[str, Any]:
    documents = store.snapshot()
    settings = documents["settings"]
    catalog = documents["catalog"]
    layout = documents["layout"]
    usage = documents["usage"]
    sync_state = documents["syncState"]
    secret_store = secrets or SecretStore()

    placements = layout.get("placements", {})
    overrides = layout.get("overrides", {})
    favorites = set(layout.get("favorites", []))
    usage_apps = usage.get("apps", {})
    apps: list[dict[str, Any]] = []

    for raw in catalog.get("apps", []):
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        app = dict(raw)
        app_id = str(app["id"])
        app_overrides = overrides.get(app_id, {})
        placement = placements.get(app_id, {})
        app["name"] = effective_name(app, app_overrides)
        app["url"] = effective_url(app, app_overrides)
        app["iconPath"] = effective_icon(app, app_overrides)
        app["iconUrl"] = file_url(app["iconPath"]) if str(app["iconPath"]).startswith("/") else ""
        app["desktopId"] = desktop_id_for(app)
        app["folderId"] = placement.get("folderId") if isinstance(placement, dict) else None
        app["position"] = placement.get("position", 0) if isinstance(placement, dict) else 0
        app["favorite"] = app_id in favorites
        app["hidden"] = bool(app_overrides.get("hidden", False))
        app_usage = usage_apps.get(app_id, {}) if isinstance(usage_apps, dict) else {}
        app["openCount"] = int(app_usage.get("openCount", 0) or 0)
        app["lastOpenedAt"] = app_usage.get("lastOpenedAt")
        apps.append(app)

    provider_status: dict[str, dict[str, Any]] = {}
    for provider in ("vercel", "github"):
        provider_settings = settings.get("providers", {}).get(provider, {})
        credential = secret_store.status(provider)
        provider_status[provider] = {
            "enabled": bool(provider_settings.get("enabled", False)),
            "configured": credential["configured"],
            "secretServiceAvailable": credential["secretServiceAvailable"],
            "settings": provider_settings,
        }

    return {
        "schemaVersion": 1,
        "apps": apps,
        "folders": layout.get("folders", []),
        "layout": {
            "rootMode": settings.get("view", {}).get("rootMode", "folders-first"),
            "layout": settings.get("view", {}).get("layout", "standard"),
            "sort": settings.get("view", {}).get("sort", "manual"),
            "showSubtitles": bool(settings.get("view", {}).get("showSubtitles", True)),
            "folderViews": layout.get("folderViews", {}),
        },
        "settings": settings,
        "usage": usage,
        "providers": provider_status,
        "syncState": sync_state,
        "pendingPlan": _pending_plan(store, sync_state.get("pendingPlanId")),
        "paths": {
            "config": str(store.paths.config_dir),
            "state": str(store.paths.state_dir),
            "cache": str(store.paths.cache_dir),
        },
    }

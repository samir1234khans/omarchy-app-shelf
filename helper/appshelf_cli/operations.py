"""Local catalogue, folder, settings and usage operations."""

from __future__ import annotations

import copy
import shutil
import sys
from pathlib import Path
from typing import Any

from .desktop import install_launcher, refresh_desktop_caches, remove_launcher
from .errors import AppShelfError
from .icons import fetch_site_metadata, install_site_icon
from .layout import (
    create_folder,
    delete_folder,
    move_folder,
    rename_folder,
    set_favorite,
    set_override,
    set_placement,
)
from .runtime import http_client_from_settings
from .security import validate_url_syntax
from .storage import Store
from .util import deep_set, json_value, normalized_domain, stable_hash, utc_now

ALLOWED_SETTING_PATHS = {
    "view.rootMode",
    "view.layout",
    "view.sort",
    "view.showSubtitles",
    "sync.onOpen",
    "sync.intervalMinutes",
    "sync.autoApplySafe",
    "sync.notifyOnChanges",
    "providers.vercel.enabled",
    "providers.vercel.teamId",
    "providers.vercel.includeProjects",
    "providers.vercel.excludeProjects",
    "providers.vercel.includePreviewDeployments",
    "providers.github.enabled",
    "providers.github.includeForks",
    "providers.github.includeArchived",
    "providers.github.includeOrganizations",
    "providers.github.excludeRepositories",
    "providers.github.maxRepositories",
    "security.allowLocalHttp",
    "security.allowPrivateNetwork",
}


def set_setting(store: Store, path: str, raw_value: Any) -> dict:
    if path not in ALLOWED_SETTING_PATHS:
        raise AppShelfError("invalid_setting", f"Unsupported setting: {path}")
    settings = store.read("settings")
    value = json_value(raw_value) if isinstance(raw_value, str) else raw_value

    if path == "view.rootMode" and value not in {
        "mixed",
        "folders-first",
        "apps-only",
        "folders-only",
        "grouped",
    }:
        raise AppShelfError("invalid_setting", "Unsupported root view mode.")
    if path == "view.layout" and value not in {"compact", "standard", "spacious", "list"}:
        raise AppShelfError("invalid_setting", "Unsupported layout mode.")
    if path == "view.sort" and value not in {
        "manual",
        "alphabetical",
        "recent",
        "added",
        "provider",
        "frequent",
        "status",
    }:
        raise AppShelfError("invalid_setting", "Unsupported sort mode.")
    if path == "sync.intervalMinutes":
        value = int(value)
        if value != 0 and value < 15:
            raise AppShelfError("invalid_setting", "Sync interval must be 0 or at least 15 minutes.")
    if path == "providers.github.maxRepositories":
        value = max(1, min(int(value), 1000))

    deep_set(settings, path, value)
    store.write("settings", settings)
    return {"path": path, "value": value}


def add_manual_webapp(
    store: Store,
    *,
    url: str,
    name: str = "",
    folder_id: str | None = None,
) -> dict:
    settings = store.read("settings")
    normalized = validate_url_syntax(
        url,
        allow_http=False,
        allow_local_http=bool(settings.get("security", {}).get("allowLocalHttp", False)),
    )
    catalog = store.read("catalog")
    layout = store.read("layout")

    for app in catalog.get("apps", []):
        if not isinstance(app, dict):
            continue
        if str(app.get("remoteUrl") or "") == normalized:
            if folder_id is not None:
                set_placement(layout, str(app["id"]), folder_id)
                store.write("layout", layout)
            return {"created": False, "app": app}

    client = http_client_from_settings(settings)
    metadata: dict[str, Any] = {}
    try:
        metadata = fetch_site_metadata(normalized, client=client)
    except Exception:
        metadata = {}
    title = " ".join(str(name or metadata.get("title") or normalized_domain(normalized)).split())
    app_id = f"web:manual:{stable_hash(normalized, 20)}"
    app = {
        "id": app_id,
        "kind": "web",
        "remoteName": title or "Web App",
        "remoteUrl": normalized,
        "sourceRepo": "",
        "providerRefs": [
            {
                "provider": "manual",
                "remoteId": stable_hash(normalized, 20),
                "status": "active",
                "lastSeenAt": utc_now(),
                "metadata": {},
            }
        ],
        "status": "active",
        "iconPath": "",
        "desktopId": "",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "lastSeenAt": utc_now(),
    }

    with store.mutation_lock():
        backup = store.create_backup()
        try:
            icon = install_site_icon(app_id, normalized, store.paths, client=client)
            if icon:
                app["iconPath"] = icon
            install_launcher(app, store.paths)
            catalog.setdefault("apps", []).append(app)
            catalog["updatedAt"] = utc_now()
            set_placement(layout, app_id, folder_id)
            store.write("catalog", catalog)
            store.write("layout", layout)
            refresh_desktop_caches(store.paths)
        except Exception:
            store.restore_backup(backup)
            try:
                remove_launcher(app, store.paths)
            except Exception:
                pass
            raise
    return {"created": True, "app": app, "backup": str(backup)}


def remove_webapp(store: Store, app_id: str) -> dict:
    catalog = store.read("catalog")
    layout = store.read("layout")
    usage = store.read("usage")
    app = next(
        (
            item
            for item in catalog.get("apps", [])
            if isinstance(item, dict) and item.get("id") == app_id
        ),
        None,
    )
    if app is None:
        raise AppShelfError("app_not_found", f"Application not found: {app_id}")

    with store.mutation_lock():
        backup = store.create_backup()
        remove_launcher(app, store.paths)
        catalog["apps"] = [
            item
            for item in catalog.get("apps", [])
            if not isinstance(item, dict) or item.get("id") != app_id
        ]
        layout.get("placements", {}).pop(app_id, None)
        layout.get("overrides", {}).pop(app_id, None)
        layout["favorites"] = [value for value in layout.get("favorites", []) if value != app_id]
        usage.get("apps", {}).pop(app_id, None)
        catalog["updatedAt"] = utc_now()
        store.write("catalog", catalog)
        store.write("layout", layout)
        store.write("usage", usage)
        refresh_desktop_caches(store.paths)
    return {"removed": app_id, "backup": str(backup)}


def update_app_override(store: Store, app_id: str, key: str, value: Any) -> dict:
    catalog = store.read("catalog")
    layout = store.read("layout")
    app = next(
        (
            item
            for item in catalog.get("apps", [])
            if isinstance(item, dict) and item.get("id") == app_id
        ),
        None,
    )
    if app is None:
        raise AppShelfError("app_not_found", f"Application not found: {app_id}")
    if key == "url" and value:
        value = validate_url_syntax(str(value), allow_http=False, allow_local_http=True)
    with store.mutation_lock():
        updated = set_override(layout, app_id, key, value)
        store.write("layout", layout)
        if key in {"name", "url", "iconPath"}:
            install_launcher(app, store.paths, updated)
            refresh_desktop_caches(store.paths)
    return {"appId": app_id, "overrides": updated}


def record_open(store: Store, app_id: str) -> dict:
    usage = store.read("usage")
    apps = usage.setdefault("apps", {})
    entry = apps.setdefault(app_id, {"openCount": 0, "lastOpenedAt": None})
    entry["openCount"] = int(entry.get("openCount", 0) or 0) + 1
    entry["lastOpenedAt"] = utc_now()
    store.write("usage", usage)
    return {"appId": app_id, **entry}


def folder_command(store: Store, action: str, **kwargs) -> dict:
    layout = store.read("layout")
    with store.mutation_lock():
        if action == "create":
            result = create_folder(layout, kwargs.get("name", ""), kwargs.get("parent_id"))
        elif action == "rename":
            result = rename_folder(layout, kwargs["folder_id"], kwargs.get("name", ""))
        elif action == "move":
            result = move_folder(layout, kwargs["folder_id"], kwargs.get("parent_id"))
        elif action == "delete":
            result = delete_folder(layout, kwargs["folder_id"])
        else:
            raise AppShelfError("invalid_action", f"Unknown folder action: {action}")
        store.write("layout", layout)
    return result


def placement_command(store: Store, app_id: str, folder_id: str | None) -> dict:
    layout = store.read("layout")
    with store.mutation_lock():
        placement = set_placement(layout, app_id, folder_id)
        store.write("layout", layout)
    return {"appId": app_id, "placement": placement}


def favorite_command(store: Store, app_id: str, enabled: bool) -> dict:
    layout = store.read("layout")
    with store.mutation_lock():
        set_favorite(layout, app_id, enabled)
        store.write("layout", layout)
    return {"appId": app_id, "favorite": enabled}


def doctor(store: Store) -> dict:
    checks = {
        "python": {
            "ok": sys.version_info >= (3, 11),
            "detail": sys.version.split()[0],
        },
        "secretTool": {
            "ok": shutil.which("secret-tool") is not None,
            "detail": shutil.which("secret-tool") or "not found",
        },
        "omarchyLaunchWebapp": {
            "ok": shutil.which("omarchy-launch-webapp") is not None,
            "detail": shutil.which("omarchy-launch-webapp") or "not found outside Omarchy host",
        },
        "gtkLaunch": {
            "ok": shutil.which("gtk-launch") is not None,
            "detail": shutil.which("gtk-launch") or "not found",
        },
        "stateWritable": {
            "ok": os_access(store.paths.state_dir),
            "detail": str(store.paths.state_dir),
        },
        "applicationsWritable": {
            "ok": os_access(store.paths.applications_dir),
            "detail": str(store.paths.applications_dir),
        },
    }
    return {
        "healthy": all(check["ok"] for key, check in checks.items() if key not in {"omarchyLaunchWebapp"}),
        "checks": checks,
    }


def os_access(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".appshelf-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False

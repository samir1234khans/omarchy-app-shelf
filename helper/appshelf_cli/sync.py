"""Provider discovery, deduplication and reviewable transactional sync."""

from __future__ import annotations

import copy
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from .desktop import (
    desktop_id_for,
    install_launcher,
    is_owned,
    refresh_desktop_caches,
)
from .errors import AppShelfError
from .icons import install_site_icon
from .providers import GitHubProvider, VercelProvider
from .providers.base import ProviderContext
from .runtime import http_client_from_settings
from .secrets import SecretStore
from .storage import Store
from .util import content_hash, normalized_domain, stable_hash, utc_now

PROVIDER_TYPES = {
    "vercel": VercelProvider,
    "github": GitHubProvider,
}


def _provider_ref(app: dict, provider: str, remote_id: str) -> dict | None:
    for ref in app.get("providerRefs", []):
        if (
            isinstance(ref, dict)
            and ref.get("provider") == provider
            and str(ref.get("remoteId")) == str(remote_id)
        ):
            return ref
    return None


def _find_match(apps: list[dict], record: dict) -> tuple[dict | None, str]:
    provider = record["provider"]
    remote_id = str(record["remoteId"])
    for app in apps:
        if _provider_ref(app, provider, remote_id):
            return app, "provider"

    source_repo = str(record.get("sourceRepo") or "").lower()
    if source_repo:
        for app in apps:
            if str(app.get("sourceRepo") or "").lower() == source_repo:
                return app, "repository"

    domain = normalized_domain(str(record.get("url") or ""))
    if domain:
        for app in apps:
            other = normalized_domain(str(app.get("remoteUrl") or app.get("url") or ""))
            if other and other == domain:
                return app, "domain"
    return None, ""


def _changed_fields(app: dict, record: dict) -> dict:
    changed: dict[str, Any] = {}
    mapping = {
        "remoteName": "name",
        "remoteUrl": "url",
        "sourceRepo": "sourceRepo",
    }
    for local_key, remote_key in mapping.items():
        next_value = record.get(remote_key) or ""
        if str(app.get(local_key) or "") != str(next_value):
            changed[local_key] = next_value
    return changed


def build_plan(
    *,
    provider: str,
    records: list[dict],
    catalog: dict,
) -> dict:
    apps = [item for item in catalog.get("apps", []) if isinstance(item, dict)]
    operations: list[dict] = []
    seen: set[str] = set()

    for record in records:
        remote_key = f"{record['provider']}:{record['remoteId']}"
        seen.add(remote_key)
        if record.get("status") != "active" or not record.get("url"):
            operations.append(
                {
                    "id": f"op:{stable_hash('unresolved:' + remote_key, 20)}",
                    "type": "unresolved",
                    "safe": False,
                    "provider": record["provider"],
                    "remoteId": str(record["remoteId"]),
                    "record": record,
                    "summary": f"{record.get('name')} has no reliable production URL",
                }
            )
            continue

        app, match_reason = _find_match(apps, record)
        if app is None:
            operations.append(
                {
                    "id": f"op:{stable_hash('add:' + remote_key, 20)}",
                    "type": "add",
                    "safe": True,
                    "provider": record["provider"],
                    "remoteId": str(record["remoteId"]),
                    "record": record,
                    "summary": f"Add {record.get('name')}",
                }
            )
            continue

        app_id = str(app["id"])
        ref = _provider_ref(app, record["provider"], str(record["remoteId"]))
        if ref is None:
            operations.append(
                {
                    "id": f"op:{stable_hash('merge:' + app_id + ':' + remote_key, 20)}",
                    "type": "merge",
                    "safe": match_reason in {"repository", "domain"},
                    "appId": app_id,
                    "provider": record["provider"],
                    "remoteId": str(record["remoteId"]),
                    "record": record,
                    "matchReason": match_reason,
                    "summary": f"Link {record.get('name')} from {record['provider']}",
                }
            )
            continue

        changes = _changed_fields(app, record)
        operation_type = "update" if changes else "refresh"
        domain_changed = (
            "remoteUrl" in changes
            and normalized_domain(str(changes["remoteUrl"]))
            != normalized_domain(str(app.get("remoteUrl") or ""))
        )
        operations.append(
            {
                "id": f"op:{stable_hash(operation_type + ':' + app_id + ':' + remote_key, 20)}",
                "type": operation_type,
                "safe": not domain_changed,
                "appId": app_id,
                "provider": record["provider"],
                "remoteId": str(record["remoteId"]),
                "record": record,
                "changes": changes,
                "summary": (
                    f"Update {record.get('name')}"
                    if changes
                    else f"Refresh {record.get('name')}"
                ),
            }
        )

    providers = {provider} if provider != "all" else {record["provider"] for record in records}
    for app in apps:
        for ref in app.get("providerRefs", []):
            if not isinstance(ref, dict) or ref.get("provider") not in providers:
                continue
            remote_key = f"{ref.get('provider')}:{ref.get('remoteId')}"
            if remote_key in seen or ref.get("status") == "stale":
                continue
            operations.append(
                {
                    "id": f"op:{stable_hash('stale:' + str(app['id']) + ':' + remote_key, 20)}",
                    "type": "stale",
                    "safe": False,
                    "appId": str(app["id"]),
                    "provider": ref.get("provider"),
                    "remoteId": str(ref.get("remoteId")),
                    "summary": f"Mark {app.get('remoteName') or app.get('name')} as stale for {ref.get('provider')}",
                }
            )

    counts = Counter(operation["type"] for operation in operations)
    created = utc_now()
    plan_id = f"sync-{created.replace(':', '-').replace('Z', '')}-{stable_hash(content_hash(operations), 8)}"
    return {
        "schemaVersion": 1,
        "id": plan_id,
        "provider": provider,
        "createdAt": created,
        "baseCatalogHash": content_hash(catalog),
        "operations": operations,
        "summary": dict(counts),
    }


def _discover_one(name: str, settings: dict, secrets: SecretStore) -> list[dict]:
    provider_settings = settings.get("providers", {}).get(name, {})
    if not provider_settings.get("enabled", False):
        return []
    provider_type = PROVIDER_TYPES[name]
    context = ProviderContext(
        settings=provider_settings,
        secrets=secrets,
        client=http_client_from_settings(settings),
    )
    return provider_type(context).discover()


def preview_sync(
    store: Store,
    provider: str = "all",
    *,
    secrets: SecretStore | None = None,
) -> dict:
    settings = store.read("settings")
    catalog = store.read("catalog")
    secret_store = secrets or SecretStore()
    names = list(PROVIDER_TYPES) if provider == "all" else [provider]
    unknown = [name for name in names if name not in PROVIDER_TYPES]
    if unknown:
        raise AppShelfError("unknown_provider", f"Unsupported provider: {unknown[0]}")

    records: list[dict] = []
    enabled_names: list[str] = []
    for name in names:
        provider_settings = settings.get("providers", {}).get(name, {})
        if not provider_settings.get("enabled", False):
            continue
        enabled_names.append(name)
        records.extend(_discover_one(name, settings, secret_store))

    if not enabled_names:
        raise AppShelfError(
            "no_providers_enabled",
            "Enable Vercel or GitHub before synchronizing.",
        )

    effective_provider = provider if provider != "all" else "all"
    plan = build_plan(provider=effective_provider, records=records, catalog=catalog)
    plan["providers"] = enabled_names
    plan_path = store.paths.state_dir / "sync-plans" / f"{plan['id']}.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    plan_path.chmod(0o600)

    state = store.read("sync-state")
    state.update(
        {
            "lastAttemptAt": utc_now(),
            "lastProvider": effective_provider,
            "lastError": None,
            "pendingPlanId": plan["id"],
        }
    )
    store.write("sync-state", state)
    return plan


def _load_plan(store: Store, plan_reference: str) -> tuple[dict, Path]:
    value = Path(str(plan_reference))
    if value.name != str(plan_reference) and not value.is_absolute():
        raise AppShelfError("invalid_plan", "Plan paths may not contain directory traversal.")
    plan_id = value.stem if value.suffix == ".json" else value.name
    if not plan_id.startswith("sync-") or "/" in plan_id or ".." in plan_id:
        raise AppShelfError("invalid_plan", "Invalid sync plan identifier.")
    path = store.paths.state_dir / "sync-plans" / f"{plan_id}.json"
    if not path.is_file():
        raise AppShelfError("plan_not_found", f"Sync plan not found: {plan_id}")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AppShelfError("invalid_plan", "Sync plan contains invalid JSON.") from exc
    if not isinstance(plan, dict) or plan.get("schemaVersion") != 1:
        raise AppShelfError("invalid_plan", "Unsupported sync plan.")
    return plan, path


def _app_for_id(catalog: dict, app_id: str) -> dict:
    for app in catalog.get("apps", []):
        if isinstance(app, dict) and app.get("id") == app_id:
            return app
    raise AppShelfError("app_not_found", f"Application not found: {app_id}")


def _reference(record: dict) -> dict:
    return {
        "provider": record["provider"],
        "remoteId": str(record["remoteId"]),
        "status": "active",
        "lastSeenAt": utc_now(),
        "metadata": record.get("metadata", {}),
    }


def _new_app(record: dict) -> dict:
    app_id = f"web:{record['provider']}:{record['remoteId']}"
    return {
        "id": app_id,
        "kind": "web",
        "remoteName": record.get("name") or record["remoteId"],
        "remoteUrl": record.get("url") or "",
        "sourceRepo": record.get("sourceRepo") or "",
        "providerRefs": [_reference(record)],
        "status": "active",
        "iconPath": "",
        "desktopId": "",
        "createdAt": utc_now(),
        "updatedAt": utc_now(),
        "lastSeenAt": utc_now(),
    }


class _DesktopTransaction:
    def __init__(self, store: Store):
        self.store = store
        self.before: dict[Path, bytes | None] = {}
        self.created_icons: set[Path] = set()

    def remember_app(self, app: dict) -> None:
        desktop_id = desktop_id_for(app)
        path = self.store.paths.applications_dir / f"{desktop_id}.desktop"
        if path not in self.before:
            self.before[path] = path.read_bytes() if path.exists() else None

    def remember_icon(self, path: str | None) -> None:
        if path:
            candidate = Path(path)
            if candidate.parent == self.store.paths.icons_dir and not candidate.exists():
                self.created_icons.add(candidate)

    def rollback(self) -> None:
        for path, payload in self.before.items():
            if payload is None:
                if path.exists() and is_owned(path):
                    path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                path.chmod(0o755)
        for icon in self.created_icons:
            icon.unlink(missing_ok=True)


def apply_sync(
    store: Store,
    plan_reference: str,
    *,
    safe_only: bool = False,
) -> dict:
    with store.mutation_lock():
        plan, plan_path = _load_plan(store, plan_reference)
        catalog = store.read("catalog")
        if content_hash(catalog) != plan.get("baseCatalogHash"):
            raise AppShelfError(
                "stale_plan",
                "The catalogue changed after this plan was created. Preview synchronization again.",
            )

        original_catalog = copy.deepcopy(catalog)
        layout = store.read("layout")
        overrides = layout.get("overrides", {})
        backup = store.create_backup()
        transaction = _DesktopTransaction(store)
        settings = store.read("settings")
        client = http_client_from_settings(settings)
        applied: list[str] = []
        skipped: list[str] = []

        try:
            for operation in plan.get("operations", []):
                if safe_only and not operation.get("safe", False):
                    skipped.append(operation["id"])
                    continue
                kind = operation.get("type")
                if kind == "unresolved":
                    skipped.append(operation["id"])
                    continue

                if kind == "add":
                    record = operation["record"]
                    app = _new_app(record)
                    transaction.remember_app(app)
                    icon = install_site_icon(
                        app["id"],
                        app["remoteUrl"],
                        store.paths,
                        client=client,
                    )
                    if icon:
                        app["iconPath"] = icon
                        transaction.created_icons.add(Path(icon))
                    install_launcher(app, store.paths, overrides.get(app["id"], {}))
                    catalog.setdefault("apps", []).append(app)
                    applied.append(operation["id"])
                    continue

                app = _app_for_id(catalog, str(operation.get("appId")))
                transaction.remember_app(app)

                if kind in {"update", "refresh"}:
                    record = operation["record"]
                    app["remoteName"] = record.get("name") or app.get("remoteName")
                    app["remoteUrl"] = record.get("url") or app.get("remoteUrl")
                    app["sourceRepo"] = record.get("sourceRepo") or app.get("sourceRepo", "")
                    ref = _provider_ref(app, record["provider"], str(record["remoteId"]))
                    if ref:
                        ref.update(_reference(record))
                    app["status"] = "active"
                    app["lastSeenAt"] = utc_now()
                    app["updatedAt"] = utc_now()
                    install_launcher(app, store.paths, overrides.get(app["id"], {}))
                    applied.append(operation["id"])
                    continue

                if kind == "merge":
                    record = operation["record"]
                    if not _provider_ref(app, record["provider"], str(record["remoteId"])):
                        app.setdefault("providerRefs", []).append(_reference(record))
                    if not app.get("sourceRepo"):
                        app["sourceRepo"] = record.get("sourceRepo") or ""
                    if not app.get("remoteUrl"):
                        app["remoteUrl"] = record.get("url") or ""
                    app["status"] = "active"
                    app["updatedAt"] = utc_now()
                    install_launcher(app, store.paths, overrides.get(app["id"], {}))
                    applied.append(operation["id"])
                    continue

                if kind == "stale":
                    ref = _provider_ref(
                        app,
                        str(operation.get("provider")),
                        str(operation.get("remoteId")),
                    )
                    if ref:
                        ref["status"] = "stale"
                        ref["staleAt"] = utc_now()
                    refs = [item for item in app.get("providerRefs", []) if isinstance(item, dict)]
                    app["status"] = (
                        "stale"
                        if refs and all(item.get("status") == "stale" for item in refs)
                        else "active"
                    )
                    app["updatedAt"] = utc_now()
                    applied.append(operation["id"])
                    continue

                skipped.append(operation["id"])

            catalog["updatedAt"] = utc_now()
            store.write("catalog", catalog)
            state = store.read("sync-state")
            state.update(
                {
                    "lastSuccessAt": utc_now(),
                    "lastError": None,
                    "pendingPlanId": None,
                }
            )
            store.write("sync-state", state)
            refresh_desktop_caches(store.paths)
            plan_path.unlink(missing_ok=True)
            return {
                "planId": plan["id"],
                "applied": applied,
                "skipped": skipped,
                "backup": str(backup),
                "catalogHash": content_hash(catalog),
            }
        except Exception:
            transaction.rollback()
            store.write("catalog", original_catalog)
            try:
                store.restore_backup(backup)
            except Exception:
                pass
            raise


def discard_plan(store: Store, plan_reference: str) -> dict:
    plan, path = _load_plan(store, plan_reference)
    path.unlink(missing_ok=True)
    state = store.read("sync-state")
    if state.get("pendingPlanId") == plan.get("id"):
        state["pendingPlanId"] = None
        store.write("sync-state", state)
    return {"discarded": plan.get("id")}

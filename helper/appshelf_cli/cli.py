"""Machine-readable App Shelf command line."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any, Callable

from . import __version__
from .errors import AppShelfError
from .operations import (
    add_manual_webapp,
    doctor,
    favorite_command,
    folder_command,
    placement_command,
    record_open,
    remove_webapp,
    set_setting,
    update_app_override,
)
from .secrets import SecretStore
from .snapshot import build_snapshot
from .storage import Store
from .sync import apply_sync, discard_plan, preview_sync


def emit(*, data: Any = None, error: AppShelfError | None = None) -> int:
    if error is None:
        payload = {"ok": True, "data": data}
        code = 0
    else:
        payload = {
            "ok": False,
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            },
        }
        code = 1
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="appshelf")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot")
    sub.add_parser("doctor")

    credentials = sub.add_parser("credentials")
    credentials_sub = credentials.add_subparsers(dest="credential_action", required=True)
    for action in ("status", "set", "remove"):
        command = credentials_sub.add_parser(action)
        command.add_argument("provider")

    settings = sub.add_parser("settings")
    settings_sub = settings.add_subparsers(dest="settings_action", required=True)
    settings_set = settings_sub.add_parser("set")
    settings_set.add_argument("path")
    settings_set.add_argument("value")

    folder = sub.add_parser("folder")
    folder_sub = folder.add_subparsers(dest="folder_action", required=True)
    folder_create = folder_sub.add_parser("create")
    folder_create.add_argument("--name", required=True)
    folder_create.add_argument("--parent-id")
    folder_rename = folder_sub.add_parser("rename")
    folder_rename.add_argument("folder_id")
    folder_rename.add_argument("--name", required=True)
    folder_move = folder_sub.add_parser("move")
    folder_move.add_argument("folder_id")
    folder_move.add_argument("--parent-id")
    folder_delete = folder_sub.add_parser("delete")
    folder_delete.add_argument("folder_id")

    placement = sub.add_parser("placement")
    placement_sub = placement.add_subparsers(dest="placement_action", required=True)
    placement_set = placement_sub.add_parser("set")
    placement_set.add_argument("app_id")
    placement_set.add_argument("--folder-id")

    favorite = sub.add_parser("favorite")
    favorite_sub = favorite.add_subparsers(dest="favorite_action", required=True)
    favorite_set = favorite_sub.add_parser("set")
    favorite_set.add_argument("app_id")
    favorite_set.add_argument("enabled", choices=("true", "false"))

    webapp = sub.add_parser("webapp")
    webapp_sub = webapp.add_subparsers(dest="webapp_action", required=True)
    webapp_add = webapp_sub.add_parser("add")
    webapp_add.add_argument("--url", required=True)
    webapp_add.add_argument("--name", default="")
    webapp_add.add_argument("--folder-id")
    webapp_remove = webapp_sub.add_parser("remove")
    webapp_remove.add_argument("app_id")
    webapp_override = webapp_sub.add_parser("override")
    webapp_override.add_argument("app_id")
    webapp_override.add_argument("key", choices=("name", "url", "iconPath", "hidden"))
    webapp_override.add_argument("value")

    usage = sub.add_parser("usage")
    usage_sub = usage.add_subparsers(dest="usage_action", required=True)
    usage_record = usage_sub.add_parser("record")
    usage_record.add_argument("app_id")

    sync = sub.add_parser("sync")
    sync_sub = sync.add_subparsers(dest="sync_action", required=True)
    sync_preview = sync_sub.add_parser("preview")
    sync_preview.add_argument("--provider", choices=("all", "vercel", "github"), default="all")
    sync_apply = sync_sub.add_parser("apply")
    sync_apply.add_argument("--plan", required=True)
    sync_apply.add_argument("--safe-only", action="store_true")
    sync_discard = sync_sub.add_parser("discard")
    sync_discard.add_argument("--plan", required=True)

    return parser


def dispatch(args: argparse.Namespace, store: Store, secrets: SecretStore) -> Any:
    if args.command == "snapshot":
        return build_snapshot(store, secrets)
    if args.command == "doctor":
        return doctor(store)

    if args.command == "credentials":
        if args.credential_action == "status":
            return secrets.status(args.provider)
        if args.credential_action == "set":
            secrets.set(args.provider)
            settings = store.read("settings")
            settings.setdefault("providers", {}).setdefault(args.provider, {})["enabled"] = True
            store.write("settings", settings)
            return secrets.status(args.provider)
        secrets.remove(args.provider)
        return secrets.status(args.provider)

    if args.command == "settings":
        return set_setting(store, args.path, args.value)

    if args.command == "folder":
        return folder_command(
            store,
            args.folder_action,
            name=getattr(args, "name", ""),
            folder_id=getattr(args, "folder_id", None),
            parent_id=getattr(args, "parent_id", None),
        )

    if args.command == "placement":
        return placement_command(store, args.app_id, args.folder_id)

    if args.command == "favorite":
        return favorite_command(store, args.app_id, args.enabled == "true")

    if args.command == "webapp":
        if args.webapp_action == "add":
            return add_manual_webapp(
                store,
                url=args.url,
                name=args.name,
                folder_id=args.folder_id,
            )
        if args.webapp_action == "remove":
            return remove_webapp(store, args.app_id)
        return update_app_override(store, args.app_id, args.key, args.value)

    if args.command == "usage":
        return record_open(store, args.app_id)

    if args.command == "sync":
        if args.sync_action == "preview":
            return preview_sync(store, args.provider, secrets=secrets)
        if args.sync_action == "apply":
            return apply_sync(store, args.plan, safe_only=args.safe_only)
        return discard_plan(store, args.plan)

    raise AppShelfError("unknown_command", "Unknown command.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = Store()
    secrets = SecretStore()
    try:
        return emit(data=dispatch(args, store, secrets))
    except AppShelfError as exc:
        return emit(error=exc)
    except KeyboardInterrupt:
        return emit(error=AppShelfError("cancelled", "Operation cancelled."))
    except Exception as exc:
        if __debug__ and "APPSHELF_DEBUG" in __import__("os").environ:
            traceback.print_exc(file=sys.stderr)
        return emit(
            error=AppShelfError(
                "internal_error",
                "App Shelf encountered an unexpected error.",
                details={"type": type(exc).__name__},
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())

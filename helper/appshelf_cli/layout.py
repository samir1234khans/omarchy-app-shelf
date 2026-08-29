"""Folder tree, placements, favorites and user overrides."""

from __future__ import annotations

from typing import Any

from .constants import MAX_FOLDER_DEPTH
from .errors import AppShelfError
from .util import slug, stable_hash, utc_now


def folder_map(layout: dict) -> dict[str, dict]:
    return {str(folder["id"]): folder for folder in layout.get("folders", []) if folder.get("id")}


def depth_of(layout: dict, folder_id: str | None) -> int:
    if not folder_id:
        return 0
    mapping = folder_map(layout)
    depth = 0
    seen: set[str] = set()
    current = folder_id
    while current:
        if current in seen:
            raise AppShelfError("folder_cycle", "The folder tree contains a cycle.")
        seen.add(current)
        folder = mapping.get(current)
        if not folder:
            raise AppShelfError("folder_not_found", f"Folder not found: {current}")
        depth += 1
        current = folder.get("parentId")
    return depth


def descendants(layout: dict, folder_id: str) -> set[str]:
    mapping = folder_map(layout)
    result: set[str] = set()
    changed = True
    while changed:
        changed = False
        for candidate, folder in mapping.items():
            if candidate in result:
                continue
            parent = folder.get("parentId")
            if parent == folder_id or parent in result:
                result.add(candidate)
                changed = True
    return result


def create_folder(layout: dict, name: str, parent_id: str | None = None) -> dict:
    clean_name = " ".join(str(name or "").split())
    if not clean_name:
        raise AppShelfError("invalid_folder_name", "Folder name cannot be empty.")
    if parent_id and parent_id not in folder_map(layout):
        raise AppShelfError("folder_not_found", f"Parent folder not found: {parent_id}")
    if depth_of(layout, parent_id) + 1 > MAX_FOLDER_DEPTH:
        raise AppShelfError(
            "folder_depth",
            f"Folders may be nested at most {MAX_FOLDER_DEPTH} levels deep.",
        )
    siblings = [
        item
        for item in layout.get("folders", [])
        if item.get("parentId") == parent_id
    ]
    folder_id = f"folder:{slug(clean_name)}-{stable_hash(clean_name + utc_now(), 8)}"
    folder = {
        "id": folder_id,
        "name": clean_name,
        "parentId": parent_id,
        "position": len(siblings),
        "createdAt": utc_now(),
    }
    layout.setdefault("folders", []).append(folder)
    return folder


def rename_folder(layout: dict, folder_id: str, name: str) -> dict:
    mapping = folder_map(layout)
    folder = mapping.get(folder_id)
    if not folder:
        raise AppShelfError("folder_not_found", f"Folder not found: {folder_id}")
    clean_name = " ".join(str(name or "").split())
    if not clean_name:
        raise AppShelfError("invalid_folder_name", "Folder name cannot be empty.")
    folder["name"] = clean_name
    return folder


def move_folder(layout: dict, folder_id: str, parent_id: str | None) -> dict:
    mapping = folder_map(layout)
    folder = mapping.get(folder_id)
    if not folder:
        raise AppShelfError("folder_not_found", f"Folder not found: {folder_id}")
    if parent_id and parent_id not in mapping:
        raise AppShelfError("folder_not_found", f"Parent folder not found: {parent_id}")
    if parent_id == folder_id or parent_id in descendants(layout, folder_id):
        raise AppShelfError("folder_cycle", "A folder cannot be moved into itself or a descendant.")
    if depth_of(layout, parent_id) + subtree_height(layout, folder_id) > MAX_FOLDER_DEPTH:
        raise AppShelfError(
            "folder_depth",
            f"Moving this folder would exceed the {MAX_FOLDER_DEPTH}-level limit.",
        )
    folder["parentId"] = parent_id
    return folder


def subtree_height(layout: dict, folder_id: str) -> int:
    mapping = folder_map(layout)
    children = [fid for fid, item in mapping.items() if item.get("parentId") == folder_id]
    if not children:
        return 1
    return 1 + max(subtree_height(layout, child) for child in children)


def delete_folder(layout: dict, folder_id: str) -> dict:
    mapping = folder_map(layout)
    folder = mapping.get(folder_id)
    if not folder:
        raise AppShelfError("folder_not_found", f"Folder not found: {folder_id}")
    parent_id = folder.get("parentId")
    layout["folders"] = [
        item for item in layout.get("folders", []) if item.get("id") != folder_id
    ]
    for child in layout["folders"]:
        if child.get("parentId") == folder_id:
            child["parentId"] = parent_id
    for placement in layout.setdefault("placements", {}).values():
        if isinstance(placement, dict) and placement.get("folderId") == folder_id:
            placement["folderId"] = parent_id
    layout.get("folderViews", {}).pop(folder_id, None)
    return folder


def set_placement(layout: dict, app_id: str, folder_id: str | None) -> dict:
    if folder_id and folder_id not in folder_map(layout):
        raise AppShelfError("folder_not_found", f"Folder not found: {folder_id}")
    placements = layout.setdefault("placements", {})
    placement = placements.setdefault(app_id, {})
    placement["folderId"] = folder_id
    siblings = [
        p for aid, p in placements.items()
        if aid != app_id and isinstance(p, dict) and p.get("folderId") == folder_id
    ]
    placement.setdefault("position", len(siblings))
    return placement


def set_favorite(layout: dict, app_id: str, enabled: bool) -> None:
    favorites = [str(value) for value in layout.get("favorites", [])]
    favorites = [value for value in favorites if value != app_id]
    if enabled:
        favorites.append(app_id)
    layout["favorites"] = favorites


def set_override(layout: dict, app_id: str, key: str, value: Any) -> dict:
    if key not in {"name", "url", "iconPath", "hidden"}:
        raise AppShelfError("invalid_override", f"Unsupported app override: {key}")
    overrides = layout.setdefault("overrides", {})
    app_overrides = overrides.setdefault(app_id, {})
    if value is None or value == "":
        app_overrides.pop(key, None)
    else:
        app_overrides[key] = value
    if not app_overrides:
        overrides.pop(app_id, None)
        return {}
    return app_overrides

#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_KINDS = {"bar-widget", "panel", "overlay", "menu", "service", "bar"}
ENTRY_KEYS = {"bar-widget": "barWidget", "panel": "panel", "overlay": "overlay", "menu": "menu", "service": "service", "bar": "bar"}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    manifest_path = ROOT / "manifest.json"
    if not manifest_path.is_file():
        fail("manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"schemaVersion", "id", "name", "version", "kinds", "entryPoints"}
    missing = sorted(required - set(manifest))
    if missing:
        fail("manifest missing fields: " + ", ".join(missing))
    if manifest["schemaVersion"] != 1:
        fail("schemaVersion must be 1")
    plugin_id = str(manifest["id"])
    if plugin_id.startswith("omarchy.") or "/" in plugin_id or ".." in plugin_id:
        fail(f"unsafe or reserved plugin id: {plugin_id}")
    for kind in manifest["kinds"]:
        if kind not in ALLOWED_KINDS:
            fail(f"unsupported kind: {kind}")
        rel = manifest["entryPoints"].get(ENTRY_KEYS[kind])
        if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in rel:
            fail(f"invalid entry point for {kind}: {rel!r}")
        if not (ROOT / rel).is_file():
            fail(f"entry point does not exist: {rel}")
    symlinks = [p.relative_to(ROOT) for p in ROOT.rglob("*") if p.is_symlink()]
    if symlinks:
        fail("symlinks are not allowed: " + ", ".join(map(str, symlinks)))
    helper = ROOT / "helper" / "appshelf"
    if helper.exists() and not os.access(helper, os.X_OK):
        fail("helper/appshelf must be executable")
    print(f"Validated {plugin_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

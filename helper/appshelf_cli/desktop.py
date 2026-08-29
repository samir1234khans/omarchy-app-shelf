"""App Shelf-owned XDG desktop entry management."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from .constants import APP_NAME
from .errors import AppShelfError
from .paths import Paths
from .security import desktop_exec_argument, desktop_value, validate_url_syntax
from .util import slug, stable_hash

OWNED_MARKER = "X-AppShelf-Managed=true"


def desktop_id_for(app: dict) -> str:
    existing = str(app.get("desktopId") or "").strip()
    if existing:
        return existing.removesuffix(".desktop")
    refs = app.get("providerRefs") or []
    if refs:
        primary = refs[0]
        provider = slug(str(primary.get("provider") or "web"))
        remote = stable_hash(str(primary.get("remoteId") or app.get("id")), 18)
        return f"appshelf-{provider}-{remote}"
    return f"appshelf-web-{stable_hash(str(app.get('id') or app.get('url')), 18)}"


def effective_name(app: dict, overrides: dict | None = None) -> str:
    return str((overrides or {}).get("name") or app.get("remoteName") or app.get("name") or "Web App")


def effective_url(app: dict, overrides: dict | None = None) -> str:
    return str((overrides or {}).get("url") or app.get("remoteUrl") or app.get("url") or "")


def effective_icon(app: dict, overrides: dict | None = None) -> str:
    return str((overrides or {}).get("iconPath") or app.get("iconPath") or "web-browser")


def render_desktop_entry(app: dict, overrides: dict | None = None) -> str:
    name = desktop_value(effective_name(app, overrides), maximum=180)
    url = validate_url_syntax(effective_url(app, overrides), allow_http=False, allow_local_http=True)
    icon = desktop_value(effective_icon(app, overrides), maximum=500)
    desktop_id = desktop_id_for(app)
    providers = sorted(
        {
            str(ref.get("provider"))
            for ref in app.get("providerRefs", [])
            if ref.get("provider")
        }
    )
    provider_value = ",".join(providers) or "manual"
    lines = [
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        f"Name={name}",
        f"Comment=Managed by {APP_NAME}",
        f"Exec=omarchy-launch-webapp {desktop_exec_argument(url)}",
        "Terminal=false",
        f"Icon={icon}",
        "StartupNotify=true",
        "Categories=Network;AppShelf;",
        OWNED_MARKER,
        f"X-AppShelf-AppId={desktop_value(app.get('id'), maximum=300)}",
        f"X-AppShelf-Provider={desktop_value(provider_value, maximum=120)}",
        f"X-AppShelf-DesktopId={desktop_value(desktop_id, maximum=120)}",
        f"X-AppShelf-CanonicalUrl={desktop_value(url, maximum=500)}",
        "",
    ]
    return "\n".join(lines)


def is_owned(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return OWNED_MARKER in content


def _atomic_write(path: Path, payload: str, mode: int = 0o755) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def install_launcher(app: dict, paths: Paths, overrides: dict | None = None) -> str:
    paths.ensure()
    desktop_id = desktop_id_for(app)
    path = paths.applications_dir / f"{desktop_id}.desktop"
    if path.exists() and not is_owned(path):
        raise AppShelfError(
            "desktop_entry_collision",
            f"Refusing to overwrite an application not owned by App Shelf: {path.name}",
        )
    _atomic_write(path, render_desktop_entry(app, overrides))
    app["desktopId"] = desktop_id
    return desktop_id


def remove_launcher(app: dict, paths: Paths) -> bool:
    desktop_id = desktop_id_for(app)
    path = paths.applications_dir / f"{desktop_id}.desktop"
    if not path.exists():
        return False
    if not is_owned(path):
        raise AppShelfError(
            "not_owned",
            f"Refusing to remove an application not owned by App Shelf: {path.name}",
        )
    path.unlink()
    icon = app.get("iconPath")
    if icon:
        icon_path = Path(str(icon))
        try:
            if icon_path.is_file() and icon_path.parent == paths.icons_dir:
                icon_path.unlink()
        except OSError:
            pass
    return True


def refresh_desktop_caches(paths: Paths) -> None:
    commands = [
        ["update-desktop-database", str(paths.applications_dir)],
        ["gtk-update-icon-cache", "-f", "-t", str(paths.data_dir / "icons/hicolor")],
    ]
    for command in commands:
        if shutil.which(command[0]):
            subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

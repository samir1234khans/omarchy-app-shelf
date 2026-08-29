"""Safe website metadata and icon discovery."""

from __future__ import annotations

import json
import mimetypes
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .constants import MAX_HTML_BYTES
from .http import HttpClient
from .paths import Paths
from .security import clean_text
from .util import stable_hash


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._inside_title = False
        self.icons: list[str] = []
        self.manifests: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._inside_title = True
            return
        if tag.lower() != "link":
            return
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        rel = values.get("rel", "").lower()
        href = values.get("href", "").strip()
        if not href:
            return
        if "manifest" in rel:
            self.manifests.append(href)
        if "icon" in rel:
            if "apple-touch-icon" in rel:
                self.icons.insert(0, href)
            else:
                self.icons.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self.title += data


_MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/gif": ".gif",
}


def _safe_icon_extension(content_type: str, url: str) -> str | None:
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime in _MIME_EXTENSIONS:
        return _MIME_EXTENSIONS[mime]
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix in {".png", ".webp", ".jpg", ".jpeg", ".ico", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    guessed = mimetypes.guess_type(url)[0]
    return _MIME_EXTENSIONS.get(str(guessed or "").lower())


def fetch_site_metadata(
    url: str,
    *,
    client: HttpClient,
) -> dict:
    response = client.request(
        url,
        headers={"Accept": "text/html,application/xhtml+xml"},
        max_bytes=MAX_HTML_BYTES,
    )
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and not response.body.lstrip().startswith(b"<"):
        return {"title": "", "iconCandidates": [], "finalUrl": response.url}

    parser = _MetadataParser()
    parser.feed(response.body.decode("utf-8", errors="replace"))
    base = response.url
    candidates = [urljoin(base, value) for value in parser.icons]

    for fallback in ("/apple-touch-icon.png", "/favicon.png", "/favicon.ico"):
        candidates.append(urljoin(base, fallback))

    # A PWA manifest often has the best available icon. Treat failures as optional.
    for manifest_url in parser.manifests[:1]:
        try:
            manifest_response = client.request(
                urljoin(base, manifest_url),
                headers={"Accept": "application/manifest+json,application/json"},
                max_bytes=MAX_HTML_BYTES,
            )
            manifest = json.loads(manifest_response.body.decode("utf-8"))
            icons = manifest.get("icons", []) if isinstance(manifest, dict) else []
            ranked = sorted(
                [item for item in icons if isinstance(item, dict) and item.get("src")],
                key=lambda item: str(item.get("sizes", "")),
                reverse=True,
            )
            candidates = [
                urljoin(manifest_response.url, str(item["src"])) for item in ranked
            ] + candidates
        except Exception:
            pass

    deduplicated: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduplicated.append(candidate)

    return {
        "title": clean_text(parser.title, maximum=180),
        "iconCandidates": deduplicated[:12],
        "finalUrl": response.url,
    }


def install_site_icon(
    app_id: str,
    url: str,
    paths: Paths,
    *,
    client: HttpClient,
) -> str | None:
    try:
        metadata = fetch_site_metadata(url, client=client)
    except Exception:
        metadata = {"iconCandidates": []}

    for candidate in metadata.get("iconCandidates", []):
        try:
            response = client.request(
                candidate,
                headers={"Accept": "image/png,image/webp,image/jpeg,image/x-icon,image/gif"},
                max_bytes=2 * 1024 * 1024,
            )
            extension = _safe_icon_extension(
                response.headers.get("content-type", ""),
                response.url,
            )
            if not extension or not response.body:
                continue
            target = paths.icons_dir / f"appshelf-{stable_hash(app_id, 20)}{extension}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.body)
            target.chmod(0o644)
            return str(target)
        except Exception:
            continue
    return None

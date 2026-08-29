"""URL, network and desktop-entry safety controls."""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

from .errors import UnsafeUrlError
from .util import normalize_http_url

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_text(value: object, *, maximum: int = 200) -> str:
    text = " ".join(str(value or "").split())
    text = _CONTROL.sub("", text)
    return text[:maximum]


def validate_url_syntax(
    url: str,
    *,
    allow_http: bool = False,
    allow_local_http: bool = False,
) -> str:
    try:
        normalized = normalize_http_url(url)
    except (TypeError, ValueError) as exc:
        raise UnsafeUrlError(str(exc)) from exc

    parts = urlsplit(normalized)
    if parts.username or parts.password:
        raise UnsafeUrlError("URLs containing embedded credentials are not allowed.")
    if parts.scheme == "http":
        host = (parts.hostname or "").lower()
        local = host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")
        if not allow_http and not (allow_local_http and local):
            raise UnsafeUrlError("Only HTTPS URLs are allowed.")
    if parts.scheme not in {"https", "http"}:
        raise UnsafeUrlError("Only HTTP and HTTPS URLs are supported.")
    return normalized


def _is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_outbound_url(
    url: str,
    *,
    allow_private: bool = False,
    allow_http: bool = False,
    allow_local_http: bool = False,
    resolver: Callable[..., list] = socket.getaddrinfo,
) -> str:
    normalized = validate_url_syntax(
        url,
        allow_http=allow_http,
        allow_local_http=allow_local_http,
    )
    host = urlsplit(normalized).hostname
    if not host:
        raise UnsafeUrlError("URL has no host.")

    try:
        literal = ipaddress.ip_address(host)
        addresses = {str(literal)}
    except ValueError:
        try:
            answers = resolver(host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafeUrlError(f"Could not resolve host: {host}") from exc
        addresses = {answer[4][0] for answer in answers}

    if not addresses:
        raise UnsafeUrlError(f"Could not resolve host: {host}")
    if not allow_private:
        blocked = [address for address in addresses if _is_blocked_ip(address)]
        if blocked:
            raise UnsafeUrlError(
                f"Private, loopback, link-local, or reserved destinations are blocked: {host}"
            )
    return normalized


def desktop_value(value: object, *, maximum: int = 500) -> str:
    """Remove control characters and line breaks from Desktop Entry fields."""
    return clean_text(value, maximum=maximum).replace("\\", "\\\\")


def desktop_exec_argument(value: str) -> str:
    """Quote one Desktop Entry Exec argument and escape field-code markers."""
    safe = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    safe = _CONTROL.sub("", safe)
    return f'"{safe}"'

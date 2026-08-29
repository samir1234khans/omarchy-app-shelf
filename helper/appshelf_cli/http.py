"""Bounded HTTP client with redirect-by-redirect SSRF validation."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .constants import HTTP_TIMEOUT_SECONDS, MAX_HTTP_BYTES, USER_AGENT
from .errors import AppShelfError, ProviderError
from .security import validate_outbound_url


@dataclass
class HttpResponse:
    body: bytes
    headers: dict[str, str]
    url: str
    status: int

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AppShelfError("invalid_response", "The server returned invalid JSON.") from exc


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, client: "HttpClient"):
        self.client = client
        super().__init__()

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if self.client.redirects >= self.client.max_redirects:
            raise AppShelfError("too_many_redirects", "The server redirected too many times.")
        self.client.redirects += 1
        target = urllib.parse.urljoin(req.full_url, newurl)
        target = self.client.validate(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


class HttpClient:
    def __init__(
        self,
        *,
        allow_private: bool = False,
        allow_http: bool = False,
        allow_local_http: bool = False,
        timeout: int = HTTP_TIMEOUT_SECONDS,
        max_bytes: int = MAX_HTTP_BYTES,
        max_redirects: int = 5,
    ):
        self.allow_private = allow_private
        self.allow_http = allow_http
        self.allow_local_http = allow_local_http
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.redirects = 0

    def validate(self, url: str) -> str:
        return validate_outbound_url(
            url,
            allow_private=self.allow_private,
            allow_http=self.allow_http,
            allow_local_http=self.allow_local_http,
        )

    def request(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        provider: str | None = None,
        max_bytes: int | None = None,
    ) -> HttpResponse:
        self.redirects = 0
        safe_url = self.validate(url)
        request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        request_headers.update(headers or {})
        request = urllib.request.Request(safe_url, headers=request_headers, method="GET")
        opener = urllib.request.build_opener(_SafeRedirectHandler(self))
        limit = max_bytes or self.max_bytes
        try:
            with opener.open(request, timeout=self.timeout) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise AppShelfError(
                        "response_too_large",
                        f"Response exceeded the {limit}-byte safety limit.",
                    )
                return HttpResponse(
                    body=body,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    url=response.geturl(),
                    status=int(getattr(response, "status", 200)),
                )
        except urllib.error.HTTPError as exc:
            message = f"HTTP {exc.code} from {urllib.parse.urlsplit(safe_url).hostname}"
            if provider:
                raise ProviderError(provider, message, status=exc.code) from exc
            raise AppShelfError("http_error", message, details={"status": exc.code}) from exc
        except urllib.error.URLError as exc:
            message = f"Network request failed: {exc.reason}"
            if provider:
                raise ProviderError(provider, message) from exc
            raise AppShelfError("network_error", message) from exc

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        provider: str | None = None,
    ) -> tuple[Any, dict[str, str]]:
        response = self.request(url, headers=headers, provider=provider)
        return response.json(), response.headers

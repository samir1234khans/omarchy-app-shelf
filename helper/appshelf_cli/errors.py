"""Typed errors returned through the JSON command envelope."""

from __future__ import annotations


class AppShelfError(Exception):
    """Expected user-facing error."""

    def __init__(self, code: str, message: str, *, details: object | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class ConcurrentMutationError(AppShelfError):
    def __init__(self) -> None:
        super().__init__(
            "busy",
            "Another App Shelf operation is already changing local state.",
        )


class UnsafeUrlError(AppShelfError):
    def __init__(self, message: str) -> None:
        super().__init__("unsafe_url", message)


class ProviderError(AppShelfError):
    def __init__(self, provider: str, message: str, *, status: int | None = None):
        details = {"provider": provider}
        if status is not None:
            details["status"] = status
        super().__init__("provider_error", message, details=details)

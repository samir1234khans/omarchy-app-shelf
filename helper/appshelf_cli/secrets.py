"""Secret Service-backed provider credentials."""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess

from .constants import SECRET_SERVICE, SUPPORTED_PROVIDERS
from .errors import AppShelfError


def _provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        raise AppShelfError("unknown_provider", f"Unsupported provider: {provider}")
    return value


class SecretStore:
    def __init__(self, executable: str = "secret-tool"):
        self.executable = executable

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def _test_secret(self, provider: str) -> str | None:
        if os.environ.get("APPSHELF_TESTING") != "1":
            return None
        return os.environ.get(f"APPSHELF_TEST_SECRET_{provider.upper()}")

    def get(self, provider: str) -> str | None:
        provider = _provider(provider)
        test = self._test_secret(provider)
        if test is not None:
            return test
        if not self.available():
            return None
        result = subprocess.run(
            [
                self.executable,
                "lookup",
                "service",
                SECRET_SERVICE,
                "provider",
                provider,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def set(self, provider: str, token: str | None = None) -> None:
        provider = _provider(provider)
        if not self.available():
            raise AppShelfError(
                "secret_service_unavailable",
                "secret-tool is unavailable; install libsecret and ensure a Secret Service is running.",
            )
        value = token if token is not None else getpass.getpass(f"{provider.title()} access token: ")
        value = str(value or "").strip()
        if not value:
            raise AppShelfError("empty_token", "The access token cannot be empty.")
        result = subprocess.run(
            [
                self.executable,
                "store",
                f"--label=Omarchy App Shelf — {provider.title()}",
                "service",
                SECRET_SERVICE,
                "provider",
                provider,
            ],
            input=value,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise AppShelfError(
                "credential_store_failed",
                result.stderr.strip() or "Secret Service rejected the credential.",
            )

    def remove(self, provider: str) -> None:
        provider = _provider(provider)
        if not self.available():
            return
        subprocess.run(
            [
                self.executable,
                "clear",
                "service",
                SECRET_SERVICE,
                "provider",
                provider,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def status(self, provider: str) -> dict:
        provider = _provider(provider)
        return {
            "provider": provider,
            "secretServiceAvailable": self.available(),
            "configured": bool(self.get(provider)),
        }

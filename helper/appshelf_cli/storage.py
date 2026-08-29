"""Atomic, locked and recoverable JSON persistence."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from . import SCHEMA_VERSION
from .defaults import catalog, layout, settings, sync_state, usage
from .errors import AppShelfError, ConcurrentMutationError
from .paths import Paths
from .util import utc_now

DEFAULT_FACTORIES: dict[str, Callable[[], dict]] = {
    "settings": settings,
    "catalog": catalog,
    "layout": layout,
    "usage": usage,
    "sync-state": sync_state,
}


class Store:
    def __init__(self, paths: Paths | None = None):
        self.paths = paths or Paths.current()
        self.paths.ensure()

    def path_for(self, name: str) -> Path:
        if name == "settings":
            return self.paths.config_dir / "settings.json"
        return self.paths.state_dir / f"{name}.json"

    def default_for(self, name: str) -> dict:
        try:
            return DEFAULT_FACTORIES[name]()
        except KeyError as exc:
            raise AppShelfError("unknown_document", f"Unknown state document: {name}") from exc

    def read(self, name: str) -> dict:
        path = self.path_for(name)
        if not path.exists():
            value = self.default_for(name)
            self.write(name, value, backup=False)
            return value

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return self._validate(name, raw)
        except (OSError, json.JSONDecodeError, AppShelfError):
            backup = path.with_suffix(path.suffix + ".last-good")
            if backup.exists():
                try:
                    raw = json.loads(backup.read_text(encoding="utf-8"))
                    value = self._validate(name, raw)
                    self.write(name, value, backup=False)
                    return value
                except (OSError, json.JSONDecodeError, AppShelfError):
                    pass
            quarantined = path.with_name(path.name + f".corrupt-{utc_now().replace(':', '-')}")
            try:
                path.replace(quarantined)
            except OSError:
                pass
            value = self.default_for(name)
            self.write(name, value, backup=False)
            return value

    def _validate(self, name: str, value: Any) -> dict:
        if not isinstance(value, dict):
            raise AppShelfError("invalid_state", f"{name}.json must contain an object")
        version = value.get("schemaVersion")
        if version != SCHEMA_VERSION:
            raise AppShelfError(
                "unsupported_schema",
                f"{name}.json uses schemaVersion {version!r}; expected {SCHEMA_VERSION}",
            )
        return value

    def write(self, name: str, value: dict, *, backup: bool = True) -> None:
        value = copy.deepcopy(value)
        value["schemaVersion"] = SCHEMA_VERSION
        path = self.path_for(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        if backup and path.exists():
            try:
                shutil.copy2(path, path.with_suffix(path.suffix + ".last-good"))
            except OSError:
                pass
        payload = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def snapshot(self) -> dict:
        return {
            "settings": self.read("settings"),
            "catalog": self.read("catalog"),
            "layout": self.read("layout"),
            "usage": self.read("usage"),
            "syncState": self.read("sync-state"),
        }

    @contextmanager
    def mutation_lock(self, *, blocking: bool = False) -> Iterator[None]:
        self.paths.lock_file.parent.mkdir(parents=True, exist_ok=True)
        with self.paths.lock_file.open("a+", encoding="utf-8") as lock:
            operation = fcntl.LOCK_EX
            if not blocking:
                operation |= fcntl.LOCK_NB
            try:
                fcntl.flock(lock.fileno(), operation)
            except BlockingIOError as exc:
                raise ConcurrentMutationError() from exc
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def create_backup(self, names: tuple[str, ...] = ("catalog", "layout", "usage", "sync-state")) -> Path:
        stamp = utc_now().replace(":", "-")
        target = self.paths.state_dir / "backups" / stamp
        target.mkdir(parents=True, exist_ok=False)
        for name in names:
            source = self.path_for(name)
            if source.exists():
                shutil.copy2(source, target / source.name)
        return target

    def restore_backup(self, backup: Path) -> None:
        if not backup.is_dir():
            raise AppShelfError("backup_not_found", f"Backup does not exist: {backup}")
        for source in backup.glob("*.json"):
            destination = (
                self.paths.config_dir / source.name
                if source.name == "settings.json"
                else self.paths.state_dir / source.name
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

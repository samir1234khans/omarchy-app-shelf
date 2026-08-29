"""XDG path resolution with deterministic test overrides."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def _xdg(name: str, fallback: str) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else _home() / fallback


@dataclass(frozen=True)
class Paths:
    config_dir: Path
    state_dir: Path
    cache_dir: Path
    data_dir: Path
    applications_dir: Path
    icons_dir: Path
    lock_file: Path

    @classmethod
    def current(cls) -> "Paths":
        config_home = _xdg("XDG_CONFIG_HOME", ".config")
        state_home = _xdg("XDG_STATE_HOME", ".local/state")
        cache_home = _xdg("XDG_CACHE_HOME", ".cache")
        data_home = _xdg("XDG_DATA_HOME", ".local/share")
        return cls(
            config_dir=config_home / "omarchy-app-shelf",
            state_dir=state_home / "omarchy-app-shelf",
            cache_dir=cache_home / "omarchy-app-shelf",
            data_dir=data_home,
            applications_dir=data_home / "applications",
            icons_dir=data_home / "icons/hicolor/256x256/apps",
            lock_file=state_home / "omarchy-app-shelf/operation.lock",
        )

    def ensure(self) -> None:
        for path in (
            self.config_dir,
            self.state_dir,
            self.cache_dir,
            self.applications_dir,
            self.icons_dir,
            self.state_dir / "backups",
            self.state_dir / "sync-plans",
            self.cache_dir / "icons",
            self.cache_dir / "metadata",
        ):
            path.mkdir(parents=True, exist_ok=True)

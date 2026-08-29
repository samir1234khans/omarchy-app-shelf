from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from helper.appshelf_cli.paths import Paths
from helper.appshelf_cli.storage import Store


@contextmanager
def isolated_store():
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        env = {
            "HOME": str(base / "home"),
            "XDG_CONFIG_HOME": str(base / "config"),
            "XDG_STATE_HOME": str(base / "state"),
            "XDG_CACHE_HOME": str(base / "cache"),
            "XDG_DATA_HOME": str(base / "data"),
            "APPSHELF_TESTING": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            store = Store(Paths.current())
            yield store

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FoundationTests(unittest.TestCase):
    def test_manifest_entry_points_exist(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        for entry in manifest["entryPoints"].values():
            self.assertTrue((ROOT / entry).is_file(), entry)

    def test_plugin_id_is_third_party(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["id"].startswith("omarchy."))
        self.assertEqual(manifest["schemaVersion"], 1)

    def test_no_symlinks(self) -> None:
        self.assertEqual([], [p for p in ROOT.rglob("*") if p.is_symlink()])


if __name__ == "__main__":
    unittest.main()

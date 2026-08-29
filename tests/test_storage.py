from __future__ import annotations

import json
import unittest

from helper.appshelf_cli.storage import Store
from tests.support import isolated_store


class StorageTests(unittest.TestCase):
    def test_defaults_are_created(self):
        with isolated_store() as store:
            snapshot = store.snapshot()
            self.assertEqual(snapshot["catalog"]["schemaVersion"], 1)
            self.assertEqual(snapshot["settings"]["view"]["layout"], "standard")

    def test_corrupt_state_recovers_to_default(self):
        with isolated_store() as store:
            path = store.path_for("catalog")
            path.write_text("{broken", encoding="utf-8")
            recovered = store.read("catalog")
            self.assertEqual(recovered["apps"], [])
            self.assertTrue(any(path.parent.glob("catalog.json.corrupt-*")))

    def test_last_good_backup_is_used(self):
        with isolated_store() as store:
            value = store.read("catalog")
            value["apps"] = [{"id": "web:test"}]
            store.write("catalog", value)
            value["apps"] = [{"id": "web:new"}]
            store.write("catalog", value)
            store.path_for("catalog").write_text("bad", encoding="utf-8")
            recovered = store.read("catalog")
            self.assertEqual(recovered["apps"][0]["id"], "web:test")


if __name__ == "__main__":
    unittest.main()

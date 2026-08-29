from __future__ import annotations

import unittest
from unittest.mock import patch

from helper.appshelf_cli.sync import apply_sync, build_plan
from helper.appshelf_cli.util import content_hash
from tests.support import isolated_store


class SyncTests(unittest.TestCase):
    def test_new_remote_record_builds_safe_add(self):
        catalog = {"schemaVersion": 1, "apps": [], "updatedAt": None}
        plan = build_plan(
            provider="vercel",
            records=[
                {
                    "provider": "vercel",
                    "remoteId": "prj_1",
                    "name": "One",
                    "url": "https://one.example/",
                    "sourceRepo": "samir/one",
                    "status": "active",
                    "metadata": {},
                }
            ],
            catalog=catalog,
        )
        self.assertEqual(plan["operations"][0]["type"], "add")
        self.assertTrue(plan["operations"][0]["safe"])

    def test_repository_match_builds_merge(self):
        catalog = {
            "schemaVersion": 1,
            "apps": [
                {
                    "id": "web:github:1",
                    "remoteName": "One",
                    "remoteUrl": "https://one.example/",
                    "sourceRepo": "samir/one",
                    "providerRefs": [{"provider": "github", "remoteId": "1", "status": "active"}],
                }
            ],
            "updatedAt": None,
        }
        plan = build_plan(
            provider="vercel",
            records=[
                {
                    "provider": "vercel",
                    "remoteId": "prj_1",
                    "name": "One",
                    "url": "https://one.example/",
                    "sourceRepo": "samir/one",
                    "status": "active",
                    "metadata": {},
                }
            ],
            catalog=catalog,
        )
        self.assertEqual(plan["operations"][0]["type"], "merge")

    def test_missing_record_is_stale_not_delete(self):
        catalog = {
            "schemaVersion": 1,
            "apps": [
                {
                    "id": "web:vercel:1",
                    "remoteName": "One",
                    "remoteUrl": "https://one.example/",
                    "providerRefs": [{"provider": "vercel", "remoteId": "1", "status": "active"}],
                }
            ],
            "updatedAt": None,
        }
        plan = build_plan(provider="vercel", records=[], catalog=catalog)
        self.assertEqual(plan["operations"][0]["type"], "stale")

    def test_apply_is_idempotent_after_repreview(self):
        with isolated_store() as store:
            catalog = store.read("catalog")
            record = {
                "provider": "vercel",
                "remoteId": "prj_1",
                "name": "One",
                "url": "https://one.example/",
                "sourceRepo": "samir/one",
                "status": "active",
                "metadata": {},
            }
            plan = build_plan(provider="vercel", records=[record], catalog=catalog)
            plan_path = store.paths.state_dir / "sync-plans" / f"{plan['id']}.json"
            import json
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with patch("helper.appshelf_cli.sync.install_site_icon", return_value=None):
                result = apply_sync(store, plan["id"])
            self.assertEqual(len(result["applied"]), 1)
            next_catalog = store.read("catalog")
            second = build_plan(provider="vercel", records=[record], catalog=next_catalog)
            self.assertEqual(second["operations"][0]["type"], "refresh")
            self.assertEqual(len(next_catalog["apps"]), 1)


if __name__ == "__main__":
    unittest.main()

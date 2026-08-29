from __future__ import annotations

import unittest

from helper.appshelf_cli.errors import AppShelfError
from helper.appshelf_cli.layout import (
    create_folder,
    delete_folder,
    move_folder,
    set_placement,
)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.layout = {
            "schemaVersion": 1,
            "folders": [],
            "placements": {},
            "overrides": {},
            "folderViews": {},
            "favorites": [],
        }

    def test_nested_folders_and_placement(self):
        root = create_folder(self.layout, "Clients")
        child = create_folder(self.layout, "Retail", root["id"])
        placement = set_placement(self.layout, "web:one", child["id"])
        self.assertEqual(placement["folderId"], child["id"])

    def test_folder_cycle_is_rejected(self):
        parent = create_folder(self.layout, "Parent")
        child = create_folder(self.layout, "Child", parent["id"])
        with self.assertRaises(AppShelfError):
            move_folder(self.layout, parent["id"], child["id"])

    def test_depth_limit_is_enforced(self):
        first = create_folder(self.layout, "One")
        second = create_folder(self.layout, "Two", first["id"])
        third = create_folder(self.layout, "Three", second["id"])
        with self.assertRaises(AppShelfError):
            create_folder(self.layout, "Four", third["id"])

    def test_delete_reparents_children_and_apps(self):
        parent = create_folder(self.layout, "Parent")
        child = create_folder(self.layout, "Child", parent["id"])
        set_placement(self.layout, "web:one", parent["id"])
        delete_folder(self.layout, parent["id"])
        self.assertIsNone(child["parentId"])
        self.assertIsNone(self.layout["placements"]["web:one"]["folderId"])


if __name__ == "__main__":
    unittest.main()

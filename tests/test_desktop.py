from __future__ import annotations

import unittest

from helper.appshelf_cli.desktop import (
    desktop_id_for,
    install_launcher,
    is_owned,
    remove_launcher,
    render_desktop_entry,
)
from helper.appshelf_cli.errors import AppShelfError
from tests.support import isolated_store


def app():
    return {
        "id": "web:vercel:prj_123",
        "remoteName": "Example",
        "remoteUrl": "https://example.com/",
        "providerRefs": [{"provider": "vercel", "remoteId": "prj_123"}],
        "iconPath": "web-browser",
    }


class DesktopTests(unittest.TestCase):
    def test_stable_desktop_id(self):
        first = desktop_id_for(app())
        changed = app()
        changed["remoteName"] = "Renamed"
        self.assertEqual(first, desktop_id_for(changed))

    def test_render_contains_ownership_marker(self):
        rendered = render_desktop_entry(app())
        self.assertIn("X-AppShelf-Managed=true", rendered)
        self.assertIn("omarchy-launch-webapp", rendered)

    def test_install_and_remove_owned_launcher(self):
        with isolated_store() as store:
            value = app()
            desktop_id = install_launcher(value, store.paths)
            path = store.paths.applications_dir / f"{desktop_id}.desktop"
            self.assertTrue(is_owned(path))
            self.assertTrue(remove_launcher(value, store.paths))
            self.assertFalse(path.exists())

    def test_refuses_to_overwrite_unowned_entry(self):
        with isolated_store() as store:
            value = app()
            path = store.paths.applications_dir / f"{desktop_id_for(value)}.desktop"
            path.write_text("[Desktop Entry]\nName=Other\n", encoding="utf-8")
            with self.assertRaises(AppShelfError):
                install_launcher(value, store.paths)


if __name__ == "__main__":
    unittest.main()

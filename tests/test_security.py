from __future__ import annotations

import socket
import unittest

from helper.appshelf_cli.errors import UnsafeUrlError
from helper.appshelf_cli.security import (
    desktop_exec_argument,
    desktop_value,
    validate_outbound_url,
    validate_url_syntax,
)


class SecurityTests(unittest.TestCase):
    def test_https_is_normalized(self):
        self.assertEqual(
            validate_url_syntax("Example.COM/path#frag"),
            "https://example.com/path",
        )

    def test_javascript_is_rejected(self):
        with self.assertRaises(UnsafeUrlError):
            validate_url_syntax("javascript:alert(1)")

    def test_http_is_rejected(self):
        with self.assertRaises(UnsafeUrlError):
            validate_url_syntax("http://example.com")

    def test_private_address_is_rejected(self):
        resolver = lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
        ]
        with self.assertRaises(UnsafeUrlError):
            validate_outbound_url("https://example.test", resolver=resolver)

    def test_public_address_is_accepted(self):
        resolver = lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ]
        self.assertEqual(
            validate_outbound_url("https://example.test", resolver=resolver),
            "https://example.test/",
        )

    def test_desktop_fields_strip_newlines(self):
        self.assertEqual(desktop_value("hello\nExec=oops"), "hello Exec=oops")

    def test_exec_percent_is_escaped(self):
        self.assertIn("%%20", desktop_exec_argument("https://example.com/%20"))


if __name__ == "__main__":
    unittest.main()

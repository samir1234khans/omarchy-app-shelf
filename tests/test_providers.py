from __future__ import annotations

import unittest

from helper.appshelf_cli.providers.base import ProviderContext
from helper.appshelf_cli.providers.github import GitHubProvider
from helper.appshelf_cli.providers.vercel import VercelProvider


class FakeSecrets:
    def get(self, provider):
        return "secret"


class VercelClient:
    def get_json(self, url, headers=None, provider=None):
        if "/v9/projects?" in url:
            return {
                "projects": [
                    {
                        "id": "prj_1",
                        "name": "portfolio",
                        "link": {"org": "samir", "repo": "portfolio"},
                    }
                ],
                "pagination": {"next": None},
            }, {}
        if "/domains" in url:
            return {"domains": [{"name": "portfolio.example", "verified": True}]}, {}
        if "/v6/deployments" in url:
            return {"deployments": [{"url": "portfolio.vercel.app"}]}, {}
        raise AssertionError(url)


class GitHubClient:
    def get_json(self, url, headers=None, provider=None):
        if "/user/repos?" in url:
            return [
                {
                    "id": 10,
                    "name": "portfolio",
                    "full_name": "samir/portfolio",
                    "homepage": "https://portfolio.example",
                    "has_pages": False,
                    "owner": {"login": "samir"},
                    "private": False,
                    "fork": False,
                    "archived": False,
                }
            ], {}
        raise AssertionError(url)


class ProviderTests(unittest.TestCase):
    def test_vercel_project_is_normalized(self):
        provider = VercelProvider(
            ProviderContext(
                settings={},
                secrets=FakeSecrets(),
                client=VercelClient(),
            )
        )
        records = provider.discover()
        self.assertEqual(records[0]["remoteId"], "prj_1")
        self.assertEqual(records[0]["url"], "https://portfolio.example/")
        self.assertEqual(records[0]["sourceRepo"], "samir/portfolio")

    def test_github_homepage_is_normalized(self):
        provider = GitHubProvider(
            ProviderContext(
                settings={"maxRepositories": 20},
                secrets=FakeSecrets(),
                client=GitHubClient(),
            )
        )
        records = provider.discover()
        self.assertEqual(records[0]["remoteId"], "10")
        self.assertEqual(records[0]["url"], "https://portfolio.example/")
        self.assertEqual(records[0]["metadata"]["urlSource"], "homepage")


if __name__ == "__main__":
    unittest.main()

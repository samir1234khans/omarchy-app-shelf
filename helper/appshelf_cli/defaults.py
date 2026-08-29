"""Default state documents."""

from __future__ import annotations

from . import SCHEMA_VERSION


def settings() -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "view": {
            "rootMode": "folders-first",
            "layout": "standard",
            "sort": "manual",
            "showSubtitles": True,
        },
        "sync": {
            "onOpen": False,
            "intervalMinutes": 360,
            "autoApplySafe": False,
            "notifyOnChanges": True,
        },
        "providers": {
            "vercel": {
                "enabled": False,
                "teamId": "",
                "includeProjects": [],
                "excludeProjects": [],
                "includePreviewDeployments": False,
            },
            "github": {
                "enabled": False,
                "includeForks": False,
                "includeArchived": False,
                "includeOrganizations": [],
                "excludeRepositories": [],
                "maxRepositories": 250,
            },
        },
        "security": {
            "allowLocalHttp": False,
            "allowPrivateNetwork": False,
        },
    }


def catalog() -> dict:
    return {"schemaVersion": SCHEMA_VERSION, "apps": [], "updatedAt": None}


def layout() -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "folders": [],
        "placements": {},
        "overrides": {},
        "folderViews": {},
        "favorites": [],
    }


def usage() -> dict:
    return {"schemaVersion": SCHEMA_VERSION, "apps": {}}


def sync_state() -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "lastAttemptAt": None,
        "lastSuccessAt": None,
        "lastProvider": None,
        "lastError": None,
        "pendingPlanId": None,
    }

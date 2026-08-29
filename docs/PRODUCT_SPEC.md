# Product Specification

## Product statement

App Shelf turns Omarchy into a coherent application workspace: native desktop programs, deployed web apps, manual websites, folders, and deployment sync all live in one fast launcher.

## Primary outcomes

1. Find any native or web application from one search surface.
2. Organise a large catalogue into folders without changing system-owned desktop entries.
3. Discover active production applications from Vercel and GitHub.
4. Review provider changes before local mutation.
5. Keep working offline from the last-known-good catalogue.

## Version 1 scope

Included: native apps, manual URLs, Vercel, GitHub, smart/manual folders, search, grid/list layouts, transactional sync, Secret Service credentials, dark design, backup and recovery.

Excluded: building arbitrary repositories, provider write operations, cloud backend, cross-device sync, stock-launcher replacement, remote-driven deletion, and OAuth server.

## Success criteria

- Warm overlay opens without spawning a second shell.
- Search remains responsive with 2,000 synthetic apps.
- Repeated sync is idempotent.
- Remote rename/domain change updates the same launcher.
- User overrides survive every sync.
- Uninstall cannot remove unrelated launchers.

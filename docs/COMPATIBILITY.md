# Omarchy Compatibility

| Channel | Ref | Commit | Inspected |
|---|---|---|---|
| Stable | `v4.0.1` | `13f18b2cb7286fb54f87daf571a031aa6af3d8f0` | 2026-08-29 |
| Development | `quattro` | `169ad00a84bba6fc76fe19bcdb822c96c86d98f0` | 2026-08-29 |

## Contracts used

- schema-version-1 third-party manifest
- `service`, `overlay`, and `bar-widget` kinds
- matching service injection
- `open(payload)` / `close()` lifecycle
- `shell.appLibrary`
- shell toggle IPC
- `omarchy-launch-webapp`
- `qs.Commons` and `qs.Ui`

## Release process

Before release, resolve latest stable and current `quattro`, run plugin validation and QML lint against both, smoke-test enable/open/close/service/bar, then update this file.

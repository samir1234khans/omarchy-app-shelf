# Security Threat Model

Omarchy plugins run as the logged-in user inside a long-lived shell. Provider data, websites, redirects, icons, names, and domains are untrusted.

## Controls

- QML uses argv arrays; provider data never becomes executable text.
- Managed desktop entries come from fixed templates and strip control characters.
- Tokens are stored in Secret Service, read through stdin, and excluded from argv, QML, logs, state, and plans.
- HTTPS is required by default; DNS and redirects are checked against private, loopback, link-local, multicast, and metadata ranges.
- Network responses have strict size, time, and redirect limits.
- Sync preview and apply are separate and revision-bound.
- Missing remote records become stale, not deleted.
- Backups precede mutation; failed batches roll back.
- Only desktop entries containing App Shelf ownership keys can be changed or removed.
- State uses `fcntl` locks and atomic fsync/rename writes.

## Non-goal

The plugin cannot sandbox Omarchy itself. Users must review plugin code before enabling it.

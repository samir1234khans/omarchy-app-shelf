# Architecture

```text
omarchy-shell
├── App Shelf service
├── App Shelf overlay
└── App Shelf bar widget
        │ safe argv Process calls
        ▼
Python standard-library helper
├── state and migrations
├── provider clients
├── reconciliation
├── desktop entries and icons
├── Secret Service adapter
└── transaction/backup layer
```

## Omarchy integration

The manifest declares `service`, `overlay`, and `bar-widget`. The overlay uses `shell.appLibrary` for native discovery, icons, hidden-entry behavior, and launches. The plugin never edits `$OMARCHY_PATH`.

## Boundary

QML owns presentation, interaction, search display, status, and process orchestration. Python owns network access, credentials, validation, reconciliation, locking, atomic state, desktop entries, icons, backup, and rollback.

Tokens are resolved inside the helper and never returned to QML.

## Helper protocol

Every command returns one JSON object with `ok`, `data`, `error`, and `meta`. QML invokes commands with argument arrays, never interpolated shell text.

## Lifecycle

1. Persistent service initializes state.
2. Overlay opens through shell IPC.
3. Overlay combines managed apps with live `shell.appLibrary` entries.
4. Mutations run through a serialized helper queue.
5. Sync creates a revision-bound review plan.
6. Apply writes a backup, mutates owned artifacts, verifies, and refreshes.

# Data Model

Remote facts and user decisions are stored separately.

## XDG paths

```text
~/.config/omarchy-app-shelf/{settings.json,layout.json}
~/.local/state/omarchy-app-shelf/{catalog.json,usage.json,sync-state.json,sync-plans/,backups/}
~/.cache/omarchy-app-shelf/{icons/,metadata/,providers/}
~/.local/share/applications/appshelf-*.desktop
~/.local/share/icons/hicolor/256x256/apps/appshelf-*.png
```

## Identity

```text
desktop:<desktop-id>
web:manual:<sha256-prefix>
web:vercel:<project-id>
web:github:<repository-id>
```

Names and URLs never form the primary identity.

## Separation

`catalog.json` stores provider IDs, remote names, canonical URLs, repository linkage, deployment metadata, and status. `layout.json` stores custom name/URL/icon, folder placement, order, favourites, hidden state, tags, and per-folder view. Provider sync must never overwrite layout decisions.

## Sync plans

Plans contain a base catalogue revision. Applying a plan after catalogue revision changes is rejected and must be previewed again.

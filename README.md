# Omarchy App Shelf

**App Shelf** is a dark, keyboard-first application library for Omarchy Quattro. It combines the local desktop application catalogue with managed web apps discovered from Vercel, GitHub, and manual URLs.

> Status: active implementation on `feat/complete-app-shelf-v1`. The first public release will be tagged after validation on the latest stable Omarchy release and the then-current `quattro` branch.

## What it provides

- Full-screen Omarchy overlay with global application and folder search
- Native Linux applications through Omarchy's shared `AppLibrary`
- Manual web-app installation using Omarchy browser app mode
- Read-only Vercel project discovery and production URL resolution
- Read-only GitHub homepage, Pages, and deployment discovery
- Smart collections, manual nested folders, favourites, recent apps, and per-folder views
- Reviewable, transactional sync plans with backups and no automatic deletion
- Optional top-bar entry with sync status
- Secret Service-backed provider credentials
- Dark-first, replaceable design tokens

## Compatibility baseline

| Target | Baseline |
|---|---|
| Stable | Omarchy `v4.0.1` |
| Stable source commit | `13f18b2cb7286fb54f87daf571a031aa6af3d8f0` |
| Development reference inspected | `quattro` at `169ad00a84bba6fc76fe19bcdb822c96c86d98f0` |
| Inspection date | 2026-08-29 |

The implementation never edits `$OMARCHY_PATH`. It installs as a third-party plugin under `~/.config/omarchy/plugins/`.

## Install

```bash
omarchy plugin add \
  https://github.com/samir1234khans/omarchy-app-shelf.git \
  --enable
```

During development:

```bash
mkdir -p ~/.config/omarchy/plugins
git clone \
  https://github.com/samir1234khans/omarchy-app-shelf.git \
  ~/.config/omarchy/plugins/io.github.samir1234khans.appshelf

cd ~/.config/omarchy/plugins/io.github.samir1234khans.appshelf
omarchy plugin validate .
omarchy-shell shell rescanPlugins
omarchy plugin enable io.github.samir1234khans.appshelf --section left
omarchy-shell shell toggle io.github.samir1234khans.appshelf '{}'
```

## Provider credentials

Credentials are stored in the desktop Secret Service, not in repository or JSON state.

```bash
helper/appshelf credentials set vercel
helper/appshelf credentials set github
helper/appshelf credentials status
```

## Safety model

- Provider calls are GET-only.
- The first provider sync is always review-first.
- Missing remote projects become **stale**, never silently deleted.
- App Shelf only removes desktop entries containing its ownership metadata.
- Tokens never enter QML properties, command-line arguments, logs, or JSON state.
- State writes are locked, atomic, backed up, and recoverable.
- Arbitrary repository code is never cloned, built, or executed.

## Documentation

See `docs/` for product, architecture, data, UX, design, provider, security, compatibility, test, and roadmap specifications.

## Licence

MIT

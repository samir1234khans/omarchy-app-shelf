# Agent Instructions

## Source of truth

Use the current repository, `docs/`, installed `$OMARCHY_PATH`, latest stable Omarchy, and current `quattro`. Never assume an older plugin API.

## Rules

- Never edit `$OMARCHY_PATH`.
- No sudo or install hooks.
- No Node, Electron, Tauri, pip dependencies, or web bundle.
- Keep Python standard-library only.
- Keep provider access read-only.
- Never expose credentials to QML, argv, logs, state, or tests.
- Use safe argv invocation and approved XDG paths.
- Only remove App Shelf-owned artifacts.
- No automatic remote deletion.
- Preserve user layout overrides.
- End every milestone with validation and a pushed checkpoint.

## Validation

```bash
python3 scripts/validate_repository.py
python3 -m unittest discover -s tests -v
omarchy plugin validate .
```

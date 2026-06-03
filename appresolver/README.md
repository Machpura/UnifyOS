# App Resolver

App Resolver v0 is a CLI prototype for managing apps through one normalized registry.

This version supports Flatpak only. It does not include a GUI, AppImage support, containers, Wine, AUR, or system components.

## Registry

By default, manifests are stored in a project-local state directory resolved from the current working directory:

```text
./.appresolver/apps/
```

This keeps v0 state out of the user's home directory. Production registry paths are future work.

Use `--registry-dir` to override the registry location for tests and development:

```bash
python -m appresolver --registry-dir /tmp/appresolver-test/apps list
```

## Requirements

- Python 3.11+
- Flatpak installed and available on `PATH`
- Flathub configured as a Flatpak remote

## Development

Install in editable mode from the repository root:

```bash
python -m pip install -e ./appresolver
```

Run tests:

```bash
pytest appresolver/tests
```

## Usage

List resolver-managed apps:

```bash
python -m appresolver list
```

Install a Flatpak app by ID:

```bash
python -m appresolver install-flatpak com.discordapp.Discord
```

Inspect the planned install without touching Flatpak or the registry:

```bash
python -m appresolver --dry-run install-flatpak com.discordapp.Discord
```

Show stored permissions:

```bash
python -m appresolver permissions com.discordapp.Discord
```

Use JSON output for future GUI/App Center code:

```bash
python -m appresolver --json list
python -m appresolver --json permissions com.discordapp.Discord
```

The same JSON flag is also accepted after `list` and `permissions`.

Uninstall a resolver-managed Flatpak app:

```bash
python -m appresolver uninstall com.discordapp.Discord
```

Inspect the planned uninstall without touching Flatpak or the registry:

```bash
python -m appresolver --dry-run uninstall com.discordapp.Discord
```

If Flatpak uninstall fails, App Resolver leaves the registry manifest in place.

## V0 Scope

Included:

- normalized app manifest model
- project-local app registry
- Flatpak install, permissions, list, and uninstall commands
- dry-run support for Flatpak install and uninstall
- JSON output for list and permissions

Not included:

- GUI/App Center
- AppImage
- containers
- Wine or Proton
- AUR
- system components
- permission enforcement beyond Flatpak-reported permission readout

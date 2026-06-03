# App Resolver

App Resolver v0 is a CLI prototype for managing apps through one normalized registry.

This version supports Flatpak installs, managed AppImage imports, and explicit Podman environment creation. It does not include a GUI, Wine, AUR, or system components.

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
- Flatpak installed and available on `PATH` for Flatpak commands
- Flathub configured as a Flatpak remote for Flatpak installs

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

Import an AppImage into project-local managed storage:

```bash
python -m appresolver import-appimage ~/Downloads/Example.AppImage
```

Inspect the planned AppImage import without copying files or writing state:

```bash
python -m appresolver --dry-run import-appimage ~/Downloads/Example.AppImage
```

Managed AppImages are copied into `./.appresolver/appimages/`, local launchers are written into `./.appresolver/launchers/`, and manifests are written into `./.appresolver/apps/`.

Define an environment record without creating runtime resources:

```bash
python -m appresolver define-environment ubuntu-24.04-default --name "Ubuntu 24.04 Default" --backend container --image ubuntu:24.04
```

Inspect the planned definition without writing state:

```bash
python -m appresolver --dry-run define-environment ubuntu-24.04-default --name "Ubuntu 24.04 Default" --backend container --image ubuntu:24.04
```

List and show environment definitions:

```bash
python -m appresolver list-environments
python -m appresolver --json list-environments
python -m appresolver show-environment ubuntu-24.04-default
python -m appresolver --json show-environment ubuntu-24.04-default
```

Delete an environment definition:

```bash
python -m appresolver delete-environment ubuntu-24.04-default
python -m appresolver --dry-run delete-environment ubuntu-24.04-default
```

Plan the Podman commands for a defined container environment without running them:

```bash
python -m appresolver plan-environment ubuntu-24.04-default
python -m appresolver --json plan-environment ubuntu-24.04-default
```

Create a defined container environment. Without `--execute`, this prints the same plan and does not call Podman or mutate state:

```bash
python -m appresolver create-environment ubuntu-24.04-default
python -m appresolver --json create-environment ubuntu-24.04-default
```

Execute the planned Podman actions and mark the environment as created only after `podman pull` and `podman create` both succeed:

```bash
python -m appresolver create-environment ubuntu-24.04-default --execute
python -m appresolver create-environment ubuntu-24.04-default --execute --json
```

Start a created or stopped environment runtime. Without `--execute`, this prints the planned start and does not call Podman or mutate state:

```bash
python -m appresolver start-environment ubuntu-24.04-default
python -m appresolver --json start-environment ubuntu-24.04-default
```

Execute the planned start and mark the environment as `running` only after `podman start` succeeds:

```bash
python -m appresolver start-environment ubuntu-24.04-default --execute
python -m appresolver start-environment ubuntu-24.04-default --execute --json
```

Stop a running environment runtime. Without `--execute`, this prints the planned stop and does not call Podman or mutate state:

```bash
python -m appresolver stop-environment ubuntu-24.04-default
python -m appresolver --json stop-environment ubuntu-24.04-default
```

Execute the planned stop and mark the environment as `stopped` only after `podman stop` succeeds:

```bash
python -m appresolver stop-environment ubuntu-24.04-default --execute
python -m appresolver stop-environment ubuntu-24.04-default --execute --json
```

Destroy a created environment runtime. Without `--execute`, this prints the planned cleanup and does not call Podman or mutate state:

```bash
python -m appresolver destroy-environment ubuntu-24.04-default
python -m appresolver --json destroy-environment ubuntu-24.04-default
```

Execute the planned cleanup and mark the environment definition back to `defined` only after `podman rm` succeeds:

```bash
python -m appresolver destroy-environment ubuntu-24.04-default --execute
python -m appresolver destroy-environment ubuntu-24.04-default --execute --json
```

`destroy-environment` removes only the runtime container. It does not delete the environment definition.
Running environments must be stopped before destroy.

Environment lifecycle:

```text
defined -> created -> running -> stopped -> running
created/stopped -> destroyed -> defined
```

Environment definitions are stored in `./.appresolver/environments/`. App Resolver does not install packages inside containers, export apps from containers, or remove containers during failure cleanup in v0.

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

Uninstall a resolver-managed app:

```bash
python -m appresolver uninstall com.discordapp.Discord
```

Inspect the planned uninstall without touching Flatpak or the registry:

```bash
python -m appresolver --dry-run uninstall com.discordapp.Discord
```

If Flatpak uninstall fails, App Resolver leaves the registry manifest in place.
If AppImage managed file removal fails, App Resolver leaves the registry manifest in place. Missing managed AppImage or launcher files are tolerated during uninstall.

## V0 Scope

Included:

- normalized app manifest model
- project-local app registry
- Flatpak install, permissions, list, and uninstall commands
- managed AppImage import and uninstall
- environment definition manifests
- Podman environment command planning
- explicit Podman environment creation with `--execute`
- explicit Podman environment start/stop lifecycle with `--execute`
- explicit Podman environment runtime cleanup with `destroy-environment --execute`
- dry-run support for Flatpak install, AppImage import, and uninstall
- JSON output for list and permissions

Not included:

- GUI/App Center
- Wine or Proton
- AUR
- system components
- AppImage execution during import
- AppImage sandboxing
- launcher export to `~/.local/share/applications`
- package installation inside containers
- app export from containers
- Podman availability checks
- permission enforcement beyond Flatpak-reported permission readout

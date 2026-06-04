# App Resolver

App Resolver v0 is a CLI prototype for managing apps through one normalized registry.

This version supports Flatpak installs, managed AppImage imports, explicit Podman environment creation, and an experimental environment-management GUI. It does not include Wine, AUR, or system components.

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
- PySide6 for the optional GUI prototype

## Development

Install in editable mode from the repository root:

```bash
python -m pip install -e ./appresolver
```

Install optional GUI dependencies:

```bash
python -m pip install -e './appresolver[gui]'
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

Launch the experimental GUI:

```bash
python -m appresolver.gui
appresolver-gui
```

The GUI uses the same resolver services as the CLI. It opens with an Apps view for normal app management and an Environments view for runtime/environment details. Execute actions ask for confirmation and run in a background Qt worker so the window remains responsive. The GUI is a prototype, not a full App Center.

Open a focused GUI dialog for one downloaded file:

```bash
python -m appresolver.gui --open ~/Downloads/Example.AppImage
appresolver-gui --open ~/Downloads/Example.AppImage
```

The focused dialog is a compact confirmation prompt with a More details section for the technical plan and actions. It does not show the full manager window and does not mutate state on startup. AppImage is the only currently executable file-open route; unsupported file types show future route or refusal messages. After a successful import, the dialog shows a success state instead of offering Import again.

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

Detect and route a downloaded installer or app file:

```bash
python -m appresolver open ~/Downloads/Example.AppImage
python -m appresolver --json open ~/Downloads/Example.AppImage
```

Execute the supported route for an AppImage:

```bash
python -m appresolver open ~/Downloads/Example.AppImage --execute
```

`open` currently imports `.AppImage` and `.appimage` files through the managed AppImage importer. It does not execute the AppImage and does not export launchers outside `./.appresolver/launchers/`.

`.deb`, `.rpm`, `.exe`, and `.flatpakref` files are detected and reported with future routes, but direct execution/import is not implemented yet. Shell scripts are refused in normal mode. Making App Resolver the default handler and full double-click installer behavior are not implemented yet.

Install user-local desktop/MIME integration so App Resolver can appear as an "Open With" target:

```bash
python -m appresolver install-desktop-integration
python -m appresolver install-desktop-integration --execute
python -m appresolver --json install-desktop-integration
```

Remove the user-local desktop/MIME integration:

```bash
python -m appresolver remove-desktop-integration
python -m appresolver remove-desktop-integration --execute
python -m appresolver --json remove-desktop-integration
```

Desktop integration is user-local only. It writes `appresolver-open.desktop` under the user applications directory and `appresolver-open.xml` under the user MIME packages directory; it does not use root, sudo, or system-wide MIME/application paths. Desktop/file-manager behavior may vary. Open With launches the focused GUI dialog, and App Resolver still requires an explicit click before importing supported files.

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
When destroy succeeds, resolver-tracked packages for that runtime are cleared from the manifest.
Running environments must be stopped before destroy.

Environment lifecycle:

```text
defined -> created -> running -> stopped -> running
created/stopped -> destroyed -> defined
```

Inspect resolver state against Podman runtime state:

```bash
python -m appresolver inspect-environment ubuntu-24.04-default
python -m appresolver --json inspect-environment ubuntu-24.04-default
```

Plan a manifest repair when resolver state and Podman runtime state diverge:

```bash
python -m appresolver reconcile-environment ubuntu-24.04-default
python -m appresolver --json reconcile-environment ubuntu-24.04-default
```

Apply the manifest repair:

```bash
python -m appresolver reconcile-environment ubuntu-24.04-default --execute
python -m appresolver reconcile-environment ubuntu-24.04-default --execute --json
```

`reconcile-environment` only updates the manifest status to match inspected runtime state. It does not create, remove, start, or stop containers. Use it to repair registry/runtime divergence after interrupted operations or manual Podman changes.

Install a native package inside an already-created managed container environment. Without `--execute`, this prints the planned Podman commands and does not call Podman or mutate state:

```bash
python -m appresolver install-package ubuntu-24.04-default curl
python -m appresolver --json install-package ubuntu-24.04-default curl
```

Execute the planned install:

```bash
python -m appresolver install-package ubuntu-24.04-default curl --execute
python -m appresolver install-package ubuntu-24.04-default curl --execute --json
```

Package installation currently supports apt-based `ubuntu:*` and `debian:*` images only. App Resolver runs `apt-get update` and `apt-get install -y PACKAGE` inside the managed container.

After a successful `install-package --execute`, App Resolver records the package in the environment manifest as a resolver-installed package:

```bash
python -m appresolver show-environment-packages ubuntu-24.04-default
python -m appresolver --json show-environment-packages ubuntu-24.04-default
```

Remove a resolver-tracked package from the managed container. Without `--execute`, this prints the planned Podman commands and does not call Podman or mutate state:

```bash
python -m appresolver remove-package ubuntu-24.04-default curl
python -m appresolver --json remove-package ubuntu-24.04-default curl
```

Execute the planned removal:

```bash
python -m appresolver remove-package ubuntu-24.04-default curl --execute
python -m appresolver remove-package ubuntu-24.04-default curl --execute --json
```

`remove-package` only removes packages tracked as installed by App Resolver. It does not run `apt autoremove`, does not purge configuration, and does not inventory packages that were installed manually inside the container.

Package tracking records only packages installed through App Resolver in the current runtime container. It does not inventory all packages in the container or query the full apt database. Destroying the runtime clears tracked installed packages because the container no longer exists. Package history and package sync/reinstall are not implemented yet.

If an environment is `created` or `stopped`, `install-package --execute` starts it first, updates the manifest status to `running`, and leaves it running for now.

Summarize an environment for future GUI/App Center consumers:

```bash
python -m appresolver environment-summary ubuntu-24.04-default
python -m appresolver --json environment-summary ubuntu-24.04-default
```

`environment-summary` compares manifest status with Podman runtime state, includes resolver-tracked packages, and reports available actions. It does not mutate the manifest and does not reconcile automatically.

Environment definitions are stored in `./.appresolver/environments/`. App Resolver does not export apps from containers or remove containers during failure cleanup in v0.

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
- file-oriented `open PATH` detection and AppImage import routing
- user-local desktop/MIME integration for App Resolver Open With routing
- manager GUI with Apps and Environments views
- focused GUI file-open dialog for one file at a time
- environment definition manifests
- Podman environment command planning
- explicit Podman environment creation with `--execute`
- explicit Podman environment start/stop lifecycle with `--execute`
- explicit Podman environment runtime cleanup with `destroy-environment --execute`
- Podman runtime state inspection and manifest reconciliation
- apt package installation/removal and resolver-installed package tracking inside ubuntu/debian managed containers
- environment summary output for future GUI/App Center consumers
- dry-run support for Flatpak install, AppImage import, and uninstall
- JSON output for resolver/app/environment commands

Not included:

- full App Center
- Wine or Proton
- AUR
- system components
- AppImage execution during import
- AppImage sandboxing
- launcher export to `~/.local/share/applications`
- system-wide MIME associations and desktop integration
- direct `.deb`, `.rpm`, `.flatpakref`, or Windows installer execution
- app export from containers
- apt autoremove or purge
- package inventory for manually installed container packages
- Podman availability checks
- permission enforcement beyond Flatpak-reported permission readout

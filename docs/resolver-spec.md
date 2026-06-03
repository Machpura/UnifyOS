# Resolver Spec

## Purpose

The Resolver is the app installation brain for the OS.

It does not try to be a universal magic installer. Its job is to take an app source, understand what it is, decide the safest supported way to install/run it, route it through the correct backend, and register the result as a normal app the user can manage.

Core rule:

> Prefer platform-native. Fall back to compatibility. Never silently mutate the host.

The Resolver exists because Linux has too many installation paths and no single product layer that answers:

- What is this app?
- Who published it?
- How trustworthy is it?
- What does it want to do?
- Where should it live?
- What permissions does it need?
- How does it update?
- How does it uninstall?
- Can it talk to other apps/environments?
- Does this require Owner Mode?

The user should not need to care whether an app came from Flatpak, AppImage, Debian package, Fedora package, Arch/AUR package, Wine, or a managed container.

The user installs apps. The OS handles formats, environments, permissions, and communication.

---

## Non-Goals

The Resolver must not become package-manager soup with a prettier UI.

For v1, it will not:

- install arbitrary shell scripts as normal apps
- allow random `.deb` or `.rpm` packages to mutate the host in Consumer Mode
- support kernel modules as regular apps
- promise that every app works
- hide dangerous behavior behind a friendly install button
- treat AUR as trustworthy by default
- claim sandboxing is perfect security
- build a full GUI before the CLI spine works
- replace Flatpak, Podman, Wine, or AppImage tooling immediately
- expose implementation details to normal users unless needed

---

## Main Components

The full app platform stack is:

```text
App Center / Installer UI
↓
App Resolver
↓
Intent Translator
↓
Policy Engine
↓
Environment Manager
↓
Communication Broker
↓
Backend Adapters
↓
App Registry + Permission Registry
↓
Host OS / Kernel / Sandboxing primitives
```

For the first prototype, build only:

```text
CLI
↓
Detector
↓
Basic Resolver
↓
Basic Policy Engine
↓
Flatpak Adapter
↓
App Registry
```

Then add AppImage. Then containers. Then Wine. Then recipes/manifests. Then communication.

---

## Component Responsibilities

### 1. App Center / Installer UI

The user-facing installer surface.

Eventually handles:

- double-clicking installers
- showing trust tier
- showing requested permissions
- showing recommended backend
- showing alternatives in Owner Mode
- install/uninstall/update/reset actions
- app permission management

Example user-facing install summary:

```text
App: SomeApp
Publisher: Unknown
Recommended install: Ubuntu Compatibility Environment
Trust level: Unverified
Requested access:
- Network
- Downloads folder
- GPU acceleration

This app will not modify the core system.
```

The UI should not ask normal users to choose between Flatpak, Podman, Distrobox, Wine, native packages, AppImage, AUR, etc.

---

### 2. App Resolver

The decision-maker.

Input examples:

- app name
- Flatpak ID
- `.flatpakref`
- `.AppImage`
- `.deb`
- `.rpm`
- `.exe`
- `.install.yaml`
- GitHub release URL
- AUR package name
- known recipe ID

The Resolver decides:

- app identity
- trust tier
- backend
- environment
- required permissions
- optional permissions
- install method
- update method
- uninstall method
- whether Owner Mode is required

The Resolver should return a structured install plan before doing anything.

Example install plan:

```yaml
app_id: com.vendor.someapp
name: SomeApp
source_type: deb
recommended_backend: deb_container
environment: ubuntu-24.04-default
trust_tier: unverified
consumer_mode_allowed: true
requires_owner_mode: false
permissions:
  files:
    downloads: read_write
  devices:
    gpu: true
  network:
    internet: true
actions:
  - create_or_reuse_environment: ubuntu-24.04-default
  - install_deb_inside_environment
  - export_desktop_launcher
  - register_app
```

---

### 3. Detector

Identifies what the user provided.

Detection sources:

- file extension
- MIME type
- file magic
- package metadata
- AppStream metadata
- embedded desktop files
- manifest files
- known recipe database

Initial supported detections:

| Input | Detection |
|---|---|
| `com.discordapp.Discord` | Flatpak app ID if found in Flatpak remotes |
| `.flatpakref` | Flatpak reference |
| `.AppImage` | AppImage portable app |
| `.deb` | Debian/Ubuntu package |
| `.rpm` | Fedora/RHEL package |
| `.exe` / `.msi` | Windows installer |
| `.install.yaml` | Declarative Resolver manifest |
| `.sh` | arbitrary script, Owner Mode only |

---

### 4. Intent Translator

The Translator converts low-level installer details into human-readable intent.

It does not need perfect omniscience. It should classify intent as:

- known
- likely
- unknown
- dangerous

Examples:

| Low-level signal | User-facing intent |
|---|---|
| Flatpak `--filesystem=xdg-download` | Access Downloads folder |
| Flatpak `--device=dri` | Use GPU acceleration |
| `.desktop` file included | Add app launcher |
| systemd user unit | Run background service |
| systemd system unit | Install system service |
| udev rule | Add hardware/device integration |
| writes to `/usr` or `/etc` | Modify system files |
| post-install script | Runs install-time code |
| opens/listens on port | Expose local network service |
| `/dev/video*` | Camera/video device access |
| `/dev/snd` / PipeWire socket | Audio access |

Translator output example:

```yaml
intents:
  desktop_launcher: known
  network_access: likely
  gpu_access: known
  downloads_access: requested
  background_service: none
  system_modification: none
  install_script_behavior: unknown
risk_flags:
  - unverified_publisher
```

---

### 5. Policy Engine

The Policy Engine decides what is allowed.

It evaluates:

- current OS mode: Consumer Mode or Owner Mode
- trust tier
- source type
- requested permissions
- backend capability
- whether the app wants host mutation
- whether the app is known/recipe-backed

Core policy:

```text
Verified Flatpak → allowed in Consumer Mode
Managed AppImage → allowed with trust warning
Deb/RPM GUI app → compatibility environment, not host install
AUR app → experimental compatibility environment, not host install
Windows installer → Wine/Proton compatibility environment
Driver/kernel module → signed system component or Owner Mode
Arbitrary shell script → Owner Mode only
Unknown root behavior → Owner Mode only
```

Policy output:

```yaml
allowed: true
requires_prompt: true
requires_owner_mode: false
reason: App can be installed in isolated Ubuntu environment without host mutation.
```

Refusal example:

```yaml
allowed: false
requires_owner_mode: true
reason: Installer wants to modify system directories and install a system service.
```

---

### 6. Environment Manager

Manages runtime bubbles where apps can live.

An Environment is a managed compatibility space, not necessarily one literal nested container.

Examples:

- Ubuntu Compatibility Environment
- Fedora Compatibility Environment
- Arch Community Environment
- Windows Compatibility Environment
- Game Modding Environment
- Python Dev Environment
- Creative Apps Environment

Responsibilities:

- create environment
- reuse environment
- install packages inside environment
- update environment
- reset environment
- delete environment
- snapshot before risky changes
- export launchers
- manage allowed files/devices/network
- report environment health

Implementation can use:

- Podman
- Distrobox-like behavior
- systemd user services
- shared volumes
- container networks
- OCI images

Avoid literal nested containers unless required. Prefer managed pods/groups of containers with shared policy.

---

### 7. Communication Broker

Controls communication between apps, environments, and the host.

This is probably v2, but the architecture should expect it.

Controls:

- open URL in default browser
- file picker / selected file access
- selected folder access
- clipboard
- notifications
- local database access
- local port exposure
- inter-environment port access
- app-to-app helper calls
- game/mod folder access
- project access groups

Example:

```text
Fedora app wants to connect to Postgres in Ubuntu Dev Environment on port 5432.
Allow?
```

The broker exists because apps sometimes need to cooperate without living in the same environment.

Principle:

> Apps should not need to live in the same place to work together. They should need declared, controlled relationships.

---

### 8. Backend Adapters

Backend adapters do the actual work.

Every backend must support the same lifecycle where possible:

```text
install
launch
update
uninstall
reset
inspect
export launcher
collect logs
```

Backends:

#### Flatpak Adapter

Preferred backend for normal verified GUI apps.

Functions:

- install by app ID
- install by flatpakref
- inspect permissions
- manage overrides
- uninstall
- update
- register manifest

#### AppImage Adapter

For portable Linux apps.

Functions:

- import into managed directory
- chmod executable
- extract metadata/icon where possible
- generate desktop launcher
- track source/version
- uninstall cleanly
- optional sandbox wrapper later

#### Container Adapter

For distro-specific GUI apps and packages.

Functions:

- create/reuse distro environment
- install `.deb` / `.rpm` inside matching environment
- install dependencies inside environment
- export launcher
- mount approved folders
- manage services
- uninstall app from environment

#### AUR Adapter

Experimental. Runs inside Arch Community Environment only.

Functions:

- create/reuse Arch environment
- build/install AUR package inside container
- export launcher
- mark app as community/experimental

Never touch host in Consumer Mode.

#### Wine/Proton Adapter

For Windows installers.

Functions:

- create prefix/environment
- run installer
- detect executable
- generate launcher
- manage runtime version
- reset/repair prefix
- uninstall

#### System Component Adapter

For deep OS functionality.

Handles:

- drivers
- codecs
- virtualization
- printer/scanner support
- VPN integration
- kernel modules
- hardware services

Only signed system components should be allowed in Consumer Mode.

#### Owner Mode Adapter

For dangerous operations.

Handles:

- arbitrary shell scripts
- native host `.deb`/`.rpm`
- custom services
- direct system modification
- kernel/module installers

Using this marks the system as Owner Modified.

---

## App Registry

The registry stores normalized app manifests.

Default prototype path:

```text
~/.local/share/appresolver/apps/{app_id}.json
```

Possible future system path:

```text
/var/lib/appresolver/apps/{app_id}.json
```

Example manifest:

```json
{
  "schema_version": 1,
  "id": "com.discordapp.Discord",
  "name": "Discord",
  "backend": "flatpak",
  "environment": null,
  "trust_tier": "community",
  "status": "installed",
  "launcher": "com.discordapp.Discord.desktop",
  "installed_from": "flathub",
  "permissions": {
    "files": {
      "downloads": "ask",
      "documents": "denied",
      "full_home": "denied"
    },
    "devices": {
      "microphone": "ask",
      "camera": "ask",
      "gpu": "allowed"
    },
    "network": {
      "internet": "allowed",
      "local_network": "ask"
    },
    "desktop": {
      "notifications": "allowed",
      "clipboard": "ask",
      "open_urls": "allowed"
    },
    "system": {
      "startup": "denied",
      "system_service": "denied",
      "admin_access": "denied"
    }
  },
  "lifecycle": {
    "install_method": "flatpak install flathub com.discordapp.Discord",
    "update_method": "flatpak update com.discordapp.Discord",
    "uninstall_method": "flatpak uninstall com.discordapp.Discord"
  }
}
```

The registry is what makes different backends feel like one app platform.

---

## Permission Vocabulary

Do not expose Linux implementation terms to normal users.

Use human language.

### File Permissions

- No file access
- Downloads
- Documents
- Pictures
- Music
- Videos
- Chosen folder
- Project folder
- Game folder
- Full home access
- System files

### Device Permissions

- GPU
- Controller
- Microphone
- Camera
- Printer/scanner
- USB device
- Serial device
- Bluetooth

### Network Permissions

- Internet
- Local network
- Host localhost
- Expose local service
- Blocked network

### Desktop Integration

- Notifications
- Clipboard
- Open links
- File associations
- Tray/background icon
- Screenshot/screen capture

### System Integration

- Run at startup
- Background service
- Modify system settings
- Install driver/kernel module
- Add hardware rules
- Admin/root access

### App/Environment Communication

- Talk to app
- Talk to environment
- Use browser login
- Use local database
- Access game folder
- Join access group

---

## Trust Tiers

### Verified

Publisher verified, signed, maintained, known-good, preferably sandboxed.

### Trusted Community

Maintained by known community packagers. Not publisher-official, but reliable enough with disclosure.

### Community

Available from community source. Needs warning. No publisher guarantee.

### Unverified

Unknown publisher/source. Allowed only through containment unless Owner Mode.

### Experimental

May break. Usually AUR/container/Wine/advanced workflows.

### System Component

Signed OS-level component. Not a normal app.

### Owner Mode

Dangerous or host-mutating install. User explicitly accepts modified system status.

---

## Backend Priority Order

Default resolver preference:

1. Verified Flatpak
2. OS-maintained recipe
3. Developer-declared manifest
4. Managed AppImage
5. Compatibility container
6. Wine/Proton wrapper
7. Signed system component
8. Owner Mode

The resolver should not blindly obey developer preference.

Developer declares intent. Resolver applies policy.

---

## Declarative Install Manifest

Long-term, developers can publish a manifest instead of a script.

Example:

```yaml
schema_version: 1
id: com.example.coolapp
name: CoolApp
publisher: Example Software
version: 1.4.2

install:
  preferred_backend: flatpak
  fallbacks:
    - appimage
    - ubuntu_container

sources:
  flatpak:
    remote: flathub
    ref: com.example.coolapp
    verified: true

  appimage:
    url: https://example.com/CoolApp-x86_64.AppImage
    sha256: abc123

permissions:
  files:
    downloads: read_write
    documents: ask
  devices:
    gpu: true
  network:
    internet: true
  desktop:
    notifications: true
    open_urls: true

integration:
  desktop_entry: true
  mime_types:
    - image/png
    - image/jpeg

updates:
  method: backend_default
  channel: stable

trust:
  publisher_verified: true
  signature: cosign/minisign/gpg/etc
```

Manifest rule:

> The install manifest is declarative data, not executable code.

No `curl | sudo bash` energy.

---

## Recipes

Recipes are maintained knowledge for known apps.

Sources:

1. OS-maintained recipes
2. Community recipes
3. Developer manifests

Recipes can define:

- best backend
- unsupported backends
- required permissions
- known issues
- hardware checks
- install steps
- launch command
- uninstall cleanup
- update behavior
- compatibility notes

Example:

```yaml
id: com.blackmagicdesign.davinciresolve
name: DaVinci Resolve
best_backend: system_component_or_container_hybrid
unsupported_backends:
  - generic_flatpak
requires:
  gpu: true
  opencl_or_cuda_or_rocm: true
  media_folder: read_write
notes:
  - Not a good generic sandbox candidate.
  - Requires GPU/runtime validation before install.
```

Recipes are how the resolver gets better over time.

---

## Access Groups

Access Groups are user-friendly shared permission sets for related apps.

Examples:

- Project: Vor RPG
- Game: Cyberpunk 2077
- Creative: Video Editing
- Dev: Python

Example group:

```yaml
id: group.game.cyberpunk2077
name: Game: Cyberpunk 2077
access:
  files:
    game_folder: read_write
    mod_staging_folder: read_write
    save_backup_folder: read_write
  devices:
    gpu: true
    controller: true
  network:
    internet: true
members:
  - steam:cypberpunk2077
  - wine:vortex-mod-manager
```

This lets apps cooperate without throwing them into one giant shared environment.

---

## CLI Prototype Commands

Initial commands:

```bash
appresolver install-flatpak com.discordapp.Discord
appresolver permissions com.discordapp.Discord
appresolver list
appresolver uninstall com.discordapp.Discord
```

Next commands:

```bash
appresolver install-appimage ~/Downloads/SomeApp.AppImage
appresolver install-deb-container ~/Downloads/someapp.deb --env ubuntu-24.04
appresolver install-rpm-container ~/Downloads/someapp.rpm --env fedora-latest
appresolver environments list
appresolver environments remove ubuntu-24.04-default
```

Later commands:

```bash
appresolver install ~/Downloads/setup.exe
appresolver install ~/Downloads/coolapp.install.yaml
appresolver inspect ~/Downloads/vendor.deb
appresolver plan ~/Downloads/vendor.deb
appresolver approve-plan plan.json
```

The `plan` command matters. The resolver should be able to show what it intends to do before doing it.

---

## MVP Build Plan

### Task 001: Registry + Flatpak

Build:

- Python CLI
- app manifest model
- registry storage
- Flatpak install command
- Flatpak permission inspection
- list command
- uninstall command
- tests for manifest read/write

Success:

```bash
appresolver install-flatpak com.discordapp.Discord
appresolver list
appresolver permissions com.discordapp.Discord
appresolver uninstall com.discordapp.Discord
```

### Task 002: AppImage Importer

Build:

- import AppImage into managed directory
- chmod executable
- generate desktop launcher
- register manifest
- uninstall removes launcher and managed file
- tests for launcher generation

Success:

```bash
appresolver install-appimage ~/Downloads/SomeApp.AppImage
```

### Task 003: Inspect/Plan System

Build:

- `inspect` command
- `plan` command
- no install until approved
- basic file-type detection
- trust/risk labels

Success:

```bash
appresolver inspect ~/Downloads/someapp.deb
appresolver plan ~/Downloads/someapp.deb
```

### Task 004: Containerized `.deb` Install

Build:

- create/reuse Ubuntu environment
- install `.deb` inside environment
- export launcher
- register app
- uninstall from environment

Success:

```bash
appresolver install-deb-container ~/Downloads/someapp.deb --env ubuntu-24.04
```

### Task 005: Containerized `.rpm` Install

Same as above, using Fedora environment.

### Task 006: Wine Installer Wrapper

Build:

- create prefix
- run installer
- detect executable manually or through prompt
- generate launcher
- register app
- reset/uninstall prefix

### Task 007: Recipes + Developer Manifest

Build:

- YAML recipe parser
- `.install.yaml` parser
- resolver plan from manifest
- signature/hash placeholders

### Task 008: Permissions Registry

Build:

- normalized permission vocabulary
- per-app permission display
- flatpak permission translation
- container permission display

### Task 009: GUI App Center Prototype

Only after CLI works.

---

## Hard Rules

1. Normal installs must not silently mutate the host.
2. Every install must produce a manifest.
3. Every app must have an uninstall path.
4. Every backend must report trust and permissions.
5. Unknown behavior must be labeled unknown, not guessed safe.
6. Arbitrary scripts are Owner Mode only.
7. AUR never touches the host in Consumer Mode.
8. System components are not normal apps.
9. Developer manifests are declarative, not executable.
10. The resolver must explain its plan before risky actions.

---

## First Codex Prompt

Use this as the first implementation prompt:

```text
We are building a prototype called App Resolver. Read docs/platform-constitution.md and docs/resolver-spec.md first. Do not build the whole OS.

Task 001:
Create a Python CLI project in ./appresolver.

Goals:
- Manage app installs through a normalized app registry.
- Store app manifests as JSON in ~/.local/share/appresolver/apps/.
- Support a Flatpak backend with:
  - install-flatpak APP_ID
  - permissions APP_ID
  - uninstall APP_ID
  - list
- Use subprocess safely.
- Do not build GUI.
- Do not support AppImage, containers, AUR, Wine, or system components yet.
- Include pytest tests for manifest creation/loading.
- Add README.md with usage examples.
- Keep functions small and boring.

Before coding, propose the file structure and implementation plan. Then implement it.
```

---

## Success Definition

The Resolver succeeds when a user can install and manage apps without understanding the backend.

The v0 success condition is tiny:

```bash
appresolver install-flatpak com.discordapp.Discord
appresolver list
appresolver permissions com.discordapp.Discord
appresolver uninstall com.discordapp.Discord
```

The v1 success condition:

```text
Most common app sources can be routed through a safe, explainable path:
- Flatpak
- AppImage
- deb-in-container
- rpm-in-container
- Wine prefix

Dangerous sources are contained, refused, or Owner Mode gated.
```

The long-term success condition:

```text
Developers can publish declarative install manifests, the OS applies policy, and users get a single coherent app install experience across Linux backends.
```

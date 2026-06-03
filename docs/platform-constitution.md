# Platform Constitution

## Purpose

This document defines the non-negotiable rules for the OS/platform project. It is not a feature wishlist. It is the set of laws the system must obey so it does not collapse into “another Linux distro with a different wallpaper.”

The goal is to build a Linux-based desktop platform that behaves like a serious consumer operating system: safe by default, recoverable by design, simple for normal users, and unlockable for owners.

The project does **not** exist to expose every Linux choice. It exists to turn Linux components into a coherent product.

---

# 1. Core Thesis

Linux is the engine, not the product.

The product is the platform layer above Linux: the app model, permissions model, update model, recovery model, environment model, support model, and user experience.

Users should interact with platform concepts, not Linux implementation details.

They should see:

- Install app
- Update system
- Restore previous version
- Manage app permissions
- Create development environment
- Fix audio/Bluetooth/game launch issue
- Enable Owner Mode

They should not need to understand:

- rpm-ostree
- package managers
- container namespaces
- Flatpak portals
- systemd units
- SELinux/AppArmor labels
- bind mounts
- DBus permissions
- distro-specific packaging

Advanced users may access those things through Owner Mode, but they are not the default language of the OS.

---

# 2. The Product Contract

The platform promises:

1. The base system is difficult to break accidentally.
2. Updates are atomic, signed, and rollbackable.
3. Normal applications do not mutate the host OS.
4. Apps install through one user-facing front door.
5. Install methods are chosen by policy, not user confusion.
6. Permissions are visible, understandable, and revocable where technically possible.
7. Dangerous system changes require Owner Mode.
8. The terminal is not required for supported normal workflows.
9. Every user-facing error should offer an action.
10. The user owns the machine and can unlock deeper control intentionally.

The platform does **not** promise:

- Every Windows/macOS/Linux app will work.
- Every installer is safe.
- Containers are magic security.
- Flatpak is perfect isolation.
- Owner Mode preserves all security guarantees.
- Random shell scripts can be safely supported as normal apps.

Honesty is part of the product.

---

# 3. Supported Modes

## 3.1 Consumer Mode

Consumer Mode is the default.

It is designed for normal use, gaming, school, work, browsing, media, and basic creativity.

Rules:

- The base OS is image-based and not casually mutated.
- Normal apps install through App Center/App Resolver.
- System-level installs are not exposed as the default path.
- Apps are sandboxed or contained when practical.
- Permissions are shown in human language.
- Updates are automatic or guided, but always rollbackable.
- Dangerous installers are blocked, contained, or routed to Owner Mode.
- No random root scripts are allowed as normal installs.
- The system should remain supportable and understandable.

Consumer Mode prioritizes:

- safety
- clarity
- recovery
- consistency
- sane defaults

## 3.2 Owner Mode

Owner Mode is an explicit unlock path.

It exists because the user owns the computer. The OS should not trap competent users in a padded cell.

Owner Mode may allow:

- host-level package installation
- advanced terminal workflows
- custom services
- custom kernel modules
- external repositories
- arbitrary scripts
- deep system configuration
- custom environments
- risky app permissions

When Owner Mode is enabled, the system status should clearly change to something like:

> Owner Modified

This is not punishment. It is truth.

Owner Mode rules:

- The OS must explain what guarantees may no longer apply.
- Owner Mode actions should be logged.
- Rollback/recovery should remain available when possible.
- Dangerous actions should still be explicit.
- The user should be able to return toward a clean state, but not all changes are guaranteed reversible.

---

# 4. Base System Rules

The base system is treated like firmware plus platform runtime.

It should include only what is needed for:

- boot
- hardware support
- display/audio/input
- networking
- sandboxing/container infrastructure
- app/runtime support
- desktop shell
- recovery
- update system
- App Center / Resolver
- Control Center
- essential system services

The base system must be:

- image-based
- signed
- reproducible
- rollbackable
- boring

The base system should not become a dumping ground for normal applications.

If something needs deep integration, it must be classified as a **System Component**, not a normal app.

Examples of System Components:

- GPU drivers
- codecs
- virtualization support
- printer/scanner backends
- VPN integration
- kernel modules
- hardware services
- filesystem support

System Components must come from trusted/signed channels or require Owner Mode.

---

# 5. App Installation Philosophy

The platform has one front door for apps: **App Center**, powered by **App Resolver**.

The user should not be asked to understand package formats unless they are in Owner Mode.

The user action is:

> Install this app.

The platform decision is:

> What is the safest supported way to make this app usable?

The resolver must prefer:

1. Verified platform-native apps
2. Known good recipes
3. Developer-declared manifests
4. Managed portable apps
5. Compatibility environments
6. Wine/Proton wrappers
7. System components
8. Owner Mode only

The resolver must not blindly install arbitrary packages onto the host.

Core principle:

> Prefer platform-native. Fall back to compatibility. Never silently mutate the host.

---

# 6. App Resolver

The App Resolver is the system that decides how an app should be installed, launched, updated, reset, and removed.

It must support a common lifecycle across backends:

- detect
- inspect
- install
- launch
- update
- uninstall
- reset
- show permissions
- collect logs
- export launcher

The resolver must produce a normalized app record no matter which backend is used.

Example app record:

```yaml
id: com.vendor.someapp
name: SomeApp
backend: ubuntu-container
environment: ubuntu-24.04-default
trust: community
status: installed
launcher: com.vendor.someapp.desktop
installed_from: someapp_amd64.deb
permissions:
  files:
    Downloads: read_write
  devices:
    - GPU
  network:
    - internet
  desktop:
    - notifications
    - open_urls
communication:
  allowed:
    - default-browser: open_urls
```

The resolver is not a universal magic installer. It is a policy-routed installer.

If an install source is too dangerous or too unknown, the resolver must say so.

---

# 7. Intent Translator

The Intent Translator converts technical installer behavior into human-readable intent.

It answers:

> What does this app appear to want to do?

It may inspect:

- Flatpak metadata
- Flatpak permissions
- AppImage metadata
- `.deb` metadata
- `.rpm` metadata
- package file lists
- post-install scripts
- desktop files
- systemd units
- udev rules
- container manifests
- Wine/Proton prefix configuration
- developer manifests
- OS recipes

Example translations:

```text
Installs .desktop file
→ Wants app launcher integration

Installs systemd user service
→ Wants background startup service

Installs udev rule
→ Wants hardware/device integration

Requests /dev/dri
→ Wants GPU access

Mounts ~/Documents
→ Wants Documents access

Exposes local port
→ Wants local service/network access

Runs root shell script
→ Wants arbitrary system modification
```

The translator must distinguish between:

- known permissions
- likely permissions
- unknown behavior
- dangerous system access

Unknown behavior must never be presented as safe.

---

# 8. Policy Engine

The Policy Engine decides what is allowed.

It answers:

- Is this allowed in Consumer Mode?
- Does this require a prompt?
- Does this require Owner Mode?
- Should this be refused?
- Should this become a System Component?
- Should this run in an Environment?
- What trust tier should the user see?

Example policy decisions:

```text
App wants Downloads access:
Allowed after prompt.

App wants GPU access:
Allowed after prompt or recipe approval.

App wants microphone:
Prompt at use or install, depending backend.

App wants full home access:
Strong warning or Owner Mode.

App wants to install a kernel module:
System Component or Owner Mode only.

App wants to run arbitrary install.sh as root:
Owner Mode only.
```

The Policy Engine is the backbone that prevents the resolver from becoming a universal malware launcher.

---

# 9. Permission Model

Linux has many permission mechanisms but lacks a unified user-facing permission product.

This platform must define one permission vocabulary.

## 9.1 File Permissions

- No file access
- Downloads
- Documents
- Pictures
- Videos
- Music
- Chosen folder
- Project folder
- Game folder
- Full home access
- System files

## 9.2 Device Permissions

- GPU
- Controller
- Microphone
- Camera
- Printer/scanner
- USB device
- Serial device
- Bluetooth

## 9.3 Network Permissions

- Internet
- Local network
- Host localhost
- Expose local service
- Blocked network
- Specific port

## 9.4 Desktop Integration

- Notifications
- Clipboard
- Open links
- File associations
- Tray/background icon
- Screenshot/screen capture
- Screen recording
- Global shortcuts

## 9.5 System Integration

- Run at startup
- Background service
- Modify system settings
- Install driver/kernel module
- Add hardware rules
- Admin/root access

## 9.6 App/Environment Communication

- Talk to app X
- Talk to environment Y
- Use default browser login
- Use local database
- Access game folder
- Join access group

Raw Linux mechanisms may exist underneath, but the user-facing permission language must remain human.

Owner Mode may expose raw details.

---

# 10. Environment Manager

The Environment Manager creates and manages runtime bubbles where apps can live.

An Environment is a managed space for related apps, services, libraries, runtimes, and package managers.

Examples:

- Ubuntu Compatibility Environment
- Fedora Compatibility Environment
- Arch Community Environment
- Windows Compatibility Environment
- Game Modding Environment
- Developer Environment
- Creative Apps Environment

Environments may be implemented using containers, pods, namespaces, Wine prefixes, Flatpak sandboxes, or other primitives.

The user-facing concept is always:

> Environment

not:

> Podman namespace with bind mounts and DBus sockets.

Environment Manager responsibilities:

- create environments
- install apps into environments
- update environments
- snapshot environments
- reset environments
- delete environments
- manage shared volumes
- manage device access
- manage launchers
- manage logs
- report environment health

Environments must be visible and manageable in Control Center.

---

# 11. Communication Broker

Apps sometimes need to talk to other apps, environments, or host services.

Hard isolation everywhere breaks real workflows.

The Communication Broker controls these relationships.

It should support:

- opening URLs in the default browser
- file picker access
- notifications
- clipboard
- local database connections
- local web server access
- selected port exposure
- access to game/project folders
- app-to-app communication
- environment-to-environment communication

The broker should distinguish between:

## User-Intent Communication

The user directly causes the action.

Examples:

- open file
- save file
- choose folder
- open link
- drag and drop
- copy and paste

This should be easy, portal-like, and narrow.

## Background Communication

Apps talk without direct user action.

Examples:

- IDE talks to language server
- app talks to local database
- mod manager watches game folder
- launcher talks to helper daemon

This requires stronger policy and visibility.

Core principle:

> Apps should not need to live in the same place to work together. They should need declared, controlled relationships.

---

# 12. Access Groups

Access Groups are user-friendly permission bundles for related workflows.

Examples:

## Project: Vor RPG

- project folder
- local dev ports
- Git tools
- language runtimes

## Game: Cyberpunk 2077

- game folder
- Proton prefix
- mod staging folder
- controller
- GPU

## Creative: Video Editing

- media drive
- render cache
- GPU
- audio devices

Apps from different backends may join the same Access Group.

This avoids forcing users to think in terms of containers, mounts, ports, and environment boundaries.

The user thinks:

> This app is allowed to participate in my Cyberpunk modding setup.

not:

> This Ubuntu container has a bind mount to this Fedora container over this namespace.

---

# 13. Backend Adapters

Backend Adapters do the actual work.

Every backend must fit the platform lifecycle:

- install
- launch
- update
- uninstall
- reset
- inspect
- export launcher
- collect logs

## 13.1 Flatpak Adapter

Preferred for verified GUI apps.

Must handle:

- install
- uninstall
- permissions
- overrides
- updates
- trust labels

## 13.2 AppImage Adapter

For portable apps.

Must handle:

- import into managed directory
- make executable
- extract metadata/icon when possible
- generate launcher
- apply sandbox wrapper when possible
- track source/version
- uninstall cleanly

AppImages should not run loose by default.

## 13.3 Container Adapter

For distro-specific userspace apps.

Examples:

- `.deb` in Ubuntu environment
- `.rpm` in Fedora environment
- AUR in Arch environment

Must handle:

- create/reuse environment
- inspect package
- install dependencies inside environment
- export launcher
- manage allowed mounts/devices
- uninstall/reset

AUR support should be experimental/community by default, not a trusted foundation.

## 13.4 Wine/Proton Adapter

For Windows `.exe` installers.

Must handle:

- create prefix/environment
- run installer
- detect launcher executable
- generate launcher
- manage runtime version
- reset/repair
- uninstall
- expose permissions honestly

## 13.5 System Component Adapter

For low-level integration.

Examples:

- drivers
- codecs
- virtualization
- VPN support
- hardware services
- printer/scanner backends
- kernel modules

System Components must come through signed/curated channels where possible.

## 13.6 Owner Mode Adapter

For dangerous operations.

Examples:

- raw `.sh` installers
- host-level `.deb`/`.rpm`
- arbitrary root scripts
- custom services
- custom kernel modules
- broad system mutation

Owner Mode Adapter must log actions and mark the system as modified.

---

# 14. Recipe and Manifest System

The platform improves over time through recipes and manifests.

## 14.1 OS-Maintained Recipes

For important apps with known best practices.

Example:

```yaml
id: com.blackmagicdesign.resolve
name: DaVinci Resolve
best_backend: system-component-container-hybrid
requires:
  - gpu_check
  - opencl_or_cuda_or_rocm
  - media_folder_access
unsupported_backends:
  - generic_flatpak
  - generic_appimage
trust: curated
```

## 14.2 Community Recipes

Useful but lower trust.

Must be labeled clearly.

## 14.3 Developer Manifests

The future target.

Developers should be able to publish declarative install manifests.

Example:

```yaml
id: com.vendor.coolapp
name: CoolApp
publisher: Example Software
install:
  preferred_backend: flatpak
  fallbacks:
    - appimage
    - ubuntu-container
sources:
  flatpak:
    ref: com.vendor.CoolApp
    remote: flathub
  appimage:
    url: https://example.com/CoolApp-x86_64.AppImage
    sha256: abc123
permissions:
  network: true
  files:
    Downloads: read_write
  devices:
    - GPU
signature: vendor-signature-here
```

Developer suggests. Resolver decides.

The manifest must be declarative, not arbitrary executable code.

Core principle:

> Do not replace every package format. Orchestrate them through a common policy layer.

---

# 15. Trust Tiers

Every app/source must show a trust tier.

Suggested tiers:

## Verified

Publisher verified, maintained, sandboxed/contained appropriately, known-good source.

## Curated

OS-maintained recipe or trusted packaging path.

## Trusted Community

Maintained by known community packagers; not publisher-official.

## Community

Available through community source, but not strongly verified.

## Compatibility

Runs through a compatibility environment because it targets another platform/distro.

## Unverified

Unknown publisher/source. Requires clear warning.

## Owner Mode

Requires broad system access or unsafe behavior.

Trust labels must not be fake security theater. They should describe source confidence and support status.

---

# 16. Updates and Recovery

Updates must be boring.

The platform update rules:

- OS updates are signed.
- OS updates are atomic.
- OS updates are rollbackable.
- Updates should not interrupt work.
- Bad updates must be recoverable.
- Stable users should receive staged/held-back updates where possible.
- Changelogs should be human-readable.

App update rules:

- Each backend must report update status.
- App Center should show updates in one place.
- App/environment updates should be reversible where practical.
- Environments should support snapshots before risky changes.

Recovery must be user-facing.

The user should see:

> Last update caused trouble? Restore previous system version.

not:

> Boot previous ostree deployment using technical terminology.

---

# 17. Control Center

Control Center is the operating system’s command room.

It must eventually manage:

- updates
- rollback
- installed apps
- app permissions
- environments
- access groups
- communication permissions
- drivers/system components
- GPU status
- gaming tools
- performance profiles
- privacy/security status
- startup apps/services
- backups
- recovery
- troubleshooting
- logs/support bundles
- accessibility
- Owner Mode

Control Center is not optional polish. It is the product shell.

Without Control Center, the project becomes another distro experiment.

---

# 18. Troubleshooting and Support

Every supported failure should lead to an action.

Bad:

> Error code 127.

Better:

> This app could not start because its compatibility environment is missing a library. Try repairing the environment.

Support tools should include:

- repair app
- reset app
- reset permissions
- repair environment
- roll back environment
- roll back OS
- collect support bundle
- show logs in human-readable form
- show raw logs in Owner Mode

Support bundles should include:

- OS version/image
- app registry
- permission registry
- environment list
- backend versions
- recent update history
- relevant logs
- GPU/driver status
- failed services

No support flow should start with “paste these 12 commands” for normal users.

---

# 19. Accessibility

Accessibility is a release requirement, not a future wishlist.

Minimum rules:

- installer must support keyboard navigation
- first-run must support keyboard navigation
- Control Center must support keyboard navigation
- screen reader setup must be available early
- high contrast mode must exist
- large text/scaling must work reliably
- reduced motion must be available
- color choices must consider colorblind users
- important status must not be conveyed only by color

If a core UI cannot be used with keyboard-only navigation, release should be blocked.

This project should not claim accessibility parity with Apple/Microsoft until earned.

---

# 20. Security Claims

Security language must be careful.

Allowed claims:

- safer by default
- recoverable by design
- sandboxed or contained where practical
- dangerous actions require explicit approval
- system updates are signed and rollbackable

Forbidden claims unless formally proven:

- unhackable
- malware-proof
- perfectly sandboxed
- impossible to break
- fully secure

Flatpak is not perfect security.
Containers are not perfect security.
Permissions are not perfect security.
Owner Mode weakens guarantees.

The platform must be honest about this.

---

# 21. Non-Goals for Early Versions

Early versions should **not** attempt to support everything.

Non-goals for v0/v1:

- perfect support for all installers
- universal safe support for arbitrary `.sh` scripts
- host-level AUR as normal behavior
- professional Adobe parity
- all anti-cheat games
- all printers/scanners
- NVIDIA perfection
- enterprise fleet management
- custom kernel from scratch
- custom display server
- custom audio stack
- custom browser engine
- custom package ecosystem

The first milestone is a coherent spine, not world conquest.

---

# 22. MVP Scope

The first prototype should be CLI-first.

No GUI at first.
No distro at first.
No full OS at first.

MVP components:

1. App Registry
2. Manifest schema
3. Detector
4. Basic Intent Translator
5. Basic Policy Engine
6. Flatpak Adapter
7. AppImage Adapter
8. Basic Container Adapter
9. CLI commands
10. Tests

Suggested commands:

```bash
appresolver install-flatpak com.discordapp.Discord
appresolver permissions com.discordapp.Discord
appresolver install-appimage ~/Downloads/SomeApp.AppImage
appresolver install-deb-container ~/Downloads/someapp.deb --env ubuntu-24.04
appresolver list
appresolver uninstall com.vendor.someapp
```

The first success condition:

> One app registry can track apps from multiple backends with normalized permissions and clean uninstall.

---

# 23. Development Rules

Development must stay boring and incremental.

Rules:

1. Every feature starts as a small ticket.
2. Every backend must support uninstall or it is not normal-mode ready.
3. Every install action must produce a registry entry.
4. Every dangerous action must go through policy.
5. Every user-facing permission must map to enforceable or clearly labeled behavior.
6. Unknown behavior must be labeled unknown.
7. Tests are required for manifest parsing and policy decisions.
8. Risky installer tests happen in disposable VMs or containers.
9. No random host mutation during development testing.
10. Codex/AI can generate code, but architecture decisions stay human-owned.

---

# 24. The Core Stack

The conceptual stack:

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
Host OS / Kernel / Sandboxing Primitives
```

Short descriptions:

- **App Center**: user-facing install/manage UI
- **Resolver**: decides install route
- **Translator**: converts technical behavior into intent
- **Policy Engine**: allows/refuses/gates actions
- **Environment Manager**: manages runtime bubbles
- **Communication Broker**: controls app/environment relationships
- **Backend Adapters**: perform installs/runs/uninstalls
- **Registry**: stores apps, permissions, environments, trust
- **Host OS**: provides kernel, drivers, sandboxing, display/audio/session

---

# 25. Final Principle

The platform exists to remove Linux chaos from the normal user path without removing ownership.

The user installs apps.
The OS handles formats, environments, permissions, updates, recovery, and communication.

The platform must be opinionated enough to be safe and coherent, but honest enough to let owners break glass.

The shortest version:

> Safe by default. Recoverable by design. Unlockable by choice.

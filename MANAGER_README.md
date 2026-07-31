# UMML-Manager User Guide

UMML-Manager is the primary desktop mod manager and development workspace for **Umamusume Pretty Derby**. It is a fork and continuation of UMML, with the original editor and loader functionality preserved through a guarded compatibility Studio while native workflows replace it piece by piece.

> **Preview:** `0.2.0~alpha18`. The application includes bounded imports, immutable versions, provider browsing, automatic preparation and source analysis, profile-scoped configuration, visual package editing, read-only veteran data tools, verified deployment, recovery journals, installation detection, and native Linux/Windows packages. Real-game and destructive-recovery testing are still required before a stable release.

## Install

### Windows portable

1. Download the `umml-manager-windows-portable` workflow artifact.
2. Extract the artifact ZIP.
3. Extract `umml-manager_0.2.0-alpha18_win64.zip`.
4. Run:

```text
UMML Manager.cmd
```

New Windows state is stored under:

```text
%LOCALAPPDATA%\UMML Manager
```

An early-preview data root is preserved when detected.

### Debian package

```bash
sudo apt install ./umml-manager_0.2.0~alpha18_amd64.deb
/usr/bin/umml-manager
```

### AppImage

```bash
chmod +x ./umml-manager_0.2.0-alpha18_x86_64.AppImage
./umml-manager_0.2.0-alpha18_x86_64.AppImage
```

The AppImage also exposes the CLI:

```bash
./umml-manager_0.2.0-alpha18_x86_64.AppImage --version
./umml-manager_0.2.0-alpha18_x86_64.AppImage --cli list
./umml-manager_0.2.0-alpha18_x86_64.AppImage --cli browse --region global
```

Linux state is stored under:

```text
~/.local/share/umml-manager
```

The Debian package and AppImage are built from the same frozen runtime. Native Windows uses a separately built portable runtime. Published artifacts receive external checksums:

```bash
sha256sum -c SHA256SUMS
```

## First launch

UMML-Manager checks saved paths, then searches supported installation layouts. The Settings page shows:

- game directory;
- `Persistent/dat` target;
- metadata source and prepared metadata identity;
- region and platform;
- installation evidence;
- diagnostics and process-inspection state.

Review the selected installation before applying a profile. Detection is evidence, not permission to write to whichever folder happens to contain enough familiar filenames.

## Interface

### Library

Library owns imported packages, versions, profiles, configuration, load order, editing, and deployment.

- Imported source versions are immutable.
- Compatible imports prepare and analyze automatically.
- There is no manual Prepare or Re-prepare maintenance step.
- **Enable / Disable** changes only the active profile.
- **Move up / Move down** changes deterministic conflict priority.
- **Configure profile** edits package-declared choices.
- **Inspect & edit** creates an editable workspace without touching the imported source.
- **New package** starts a creator workspace.
- **Apply profile** remains explicit and is blocked while the game is running or the plan has blockers.

### Discover

Discover provides:

- Global and Japan GameBanana browsing;
- exact downloadable-file selection;
- bounded preview images;
- verified archive provenance;
- local Downloads/custom-folder scans;
- safe archive and local-folder validation.

Downloading and importing never deploys a mod.

### Conflicts

Conflicts shows the complete resolved plan:

- enabled package versions;
- selected profile choices;
- final target ownership;
- winning and shadowed claims;
- missing dependencies;
- incompatibilities;
- wrong region or installation;
- invalid relative load order;
- stale or unverified preparation;
- external changes and recovery blockers.

Later enabled entries win ordinary file conflicts unless package policy blocks the plan.

### Studio

Studio currently contains:

- the original UMML editor and loader tools behind process guards;
- native package and creator entry points;
- the read-only Veteran Roster workspace.

Legacy tools remain available until native replacements reach feature parity and pass restoration tests. They are compatibility code, not the design model for new pages.

### Veteran Roster

Veteran Roster imports externally produced JSON from the `umadump` / `UmaExtractor` community family.

It can:

- import classic `data.json`;
- import Werseter `trained_chara_data.json`;
- reject support-card, trophy, friend, card, and replay outputs masquerading as rosters;
- remove known viewer/account identifiers and account-name fields recursively;
- store immutable timestamped snapshots;
- search, sort, inspect, and export scrubbed records;
- launch a user-selected external extractor in an isolated inbox.

Upstream extractor code and binaries are not bundled when their repository does not declare a compatible project-wide license. See [docs/UMAEXTRACTOR_INTEGRATION.md](docs/UMAEXTRACTOR_INTEGRATION.md).

### Settings

Settings manages:

- installation selection and automatic detection;
- Manager data and workspace locations;
- Light, Dark, and System appearance;
- diagnostics;
- metadata preparation identity;
- external tool paths.

Manager-owned windows should open centered, raised, focused, and briefly topmost so new dialogs do not hide behind the main window like paperwork attempting escape.

## Player workflow

1. Launch UMML-Manager.
2. Confirm the detected installation in Settings.
3. Import a mod from Discover or a local package.
4. Wait for automatic preparation and source analysis to report **Ready**.
5. Enable the mod in a profile.
6. Configure package options, when present.
7. Set load order.
8. Review Conflicts.
9. Close the game.
10. Apply the profile.

To switch setups, select another profile and apply it. To return to vanilla, apply an empty profile or use the verified restoration path shown by the interface.

## Creator workflow

1. Use **New package** for a fresh workspace, or **Inspect & edit** on an imported mod.
2. Add or review source bundles under the workspace `assets/` directory.
3. Review detected final targets, content types, parts, characters, and dresses.
4. Edit package identity, regions, dependencies, incompatibilities, relative order, tags, and notes.
5. Add profile-scoped variants or optional components.
6. Validate the workspace.
7. Import it as a new immutable version.
8. Test it in a dedicated profile, including conflict preview, Apply, profile switching, and vanilla restoration.
9. Publish the package with its manifest, version, credits, and compatibility information.

See [docs/MOD_CREATOR_GUIDE.md](docs/MOD_CREATOR_GUIDE.md) and [docs/MANAGER_MOD_MANIFEST.md](docs/MANAGER_MOD_MANIFEST.md).

## Automatic preparation

Preparation is an internal background stage that converts creator-facing inputs into a verified deployable view.

The user does not manage it manually. UMML-Manager automatically queues:

- newly imported compatible packages;
- packages prepared with older metadata;
- stale metadata fingerprints;
- older preparation layouts requiring migration;
- source analysis that has not yet completed.

Preparation never writes game files. A failure preserves the imported source and any prior verified prepared cache, continues the remaining queue, and reports an actionable package-specific issue.

## Safety and recovery

UMML-Manager uses:

- target-bound vanilla baselines;
- immutable imported versions;
- isolated prepared payloads;
- deterministic planning;
- path containment and SHA-256 verification;
- process inspection before mutation;
- durable transaction journals;
- rollback and recovery snapshots;
- active-state verification;
- external-change protection;
- fail-closed critical-state handling.

Corrupt preferences are quarantined and reset with their original bytes preserved. Corrupt deployment, baseline, profile, library, or recovery state blocks mutation rather than silently starting over.

## Historical source-install cleanup

Early previews mixed application code with Manager state. Do not use an old alpha1 `uninstall-manager.sh`, because it could delete the mixed directory.

Remove only stale launchers while preserving the library and recovery state:

```bash
rm -f ~/.local/bin/umml-manager ~/.local/bin/umml-manager-cli
rm -f ~/.local/share/applications/io.github.evelynlimab.ummlmanager.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
hash -r
```

Current source installs use:

```text
application: ~/.local/share/umml-manager-app
state:       ~/.local/share/umml-manager
```

## Command-line interface

The CLI and GUI use the same store, resolver, safety checks, and deployment engine.

```bash
umml-manager-cli --help
umml-manager-cli list
umml-manager-cli doctor
umml-manager-cli network-smoke
umml-manager-cli self-test
```

Do not use the CLI as a secret back door around GUI blockers. It is deliberately equally paranoid.

## Further documentation

- [Project vision](docs/PROJECT_VISION.md)
- [Mod creator guide](docs/MOD_CREATOR_GUIDE.md)
- [Architecture](docs/MANAGER_ARCHITECTURE.md)
- [Manifest reference](docs/MANAGER_MOD_MANIFEST.md)
- [Development](docs/MANAGER_DEVELOPMENT.md)
- [Packaging](docs/PACKAGING.md)
- [Security](SECURITY.md)
- [Release checklist](docs/MANAGER_RELEASE_CHECKLIST.md)

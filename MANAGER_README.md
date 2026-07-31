# Uma Mod Manager user guide

**Uma Mod Manager** is the primary desktop mod manager and creator workspace in this repository. It is a fork and continuation of UMML, with the original editor and loader functionality preserved through a guarded compatibility Studio while tested native workflows replace it piece by piece.

> **Community Test:** `0.2.0~alpha19`. The application includes bounded imports, immutable versions, provider browsing, automatic preparation and source analysis, profile-scoped configuration, visual package editing, read-only veteran-data tools, verified deployment, recovery journals, installation detection, privacy-scrubbed support bundles, and native Linux/Windows packages. Real-game and destructive-recovery testing are still required before a stable release.

Read the [alpha19 release notes](docs/releases/0.2.0-alpha.19.md) and [Testing and feedback](docs/TESTING_AND_FEEDBACK.md) before testing this build.

## Naming and compatibility

The public product and repository are named **Uma Mod Manager**. Existing technical identifiers remain unchanged during the migration so upgrades do not abandon user data or install a second application by accident:

```text
Linux package:     umml-manager
CLI:               umml-manager-cli
Python module:     umml_manager
Desktop/AppStream: io.github.evelynlimab.ummlmanager
Windows data root: %LOCALAPPDATA%\UMML Manager
Linux data root:   ~/.local/share/umml-manager
```

See [Branding and compatibility](docs/BRANDING_AND_COMPATIBILITY.md).

## Install

### Windows portable

1. Download the exact Community Test ZIP or a successful Windows workflow artifact.
2. Verify its SHA-256.
3. Extract the application ZIP.
4. Run:

```text
Uma Mod Manager.cmd
```

A compatibility launcher named `UMML Manager.cmd` remains during the migration window. No Python installation is required for the packaged build. Keep the previous extracted folder for rollback.

### Debian package

```bash
sudo apt install ./umml-manager_0.2.0~alpha19_amd64.deb
/usr/bin/umml-manager
```

The technical package name remains `umml-manager`, so an alpha19 package upgrades an earlier Manager package in place and continues using the same data root.

### AppImage

```bash
chmod +x ./umml-manager_0.2.0-alpha.19_x86_64.AppImage
./umml-manager_0.2.0-alpha.19_x86_64.AppImage
```

The AppImage also exposes the CLI:

```bash
./umml-manager_0.2.0-alpha.19_x86_64.AppImage --version
./umml-manager_0.2.0-alpha.19_x86_64.AppImage --cli list
./umml-manager_0.2.0-alpha.19_x86_64.AppImage --cli doctor
```

The Debian package, AppImage, and native Windows portable are built and validated independently. Verify published artifacts with:

```bash
sha256sum -c SHA256SUMS
```

## First launch

Uma Mod Manager checks saved paths, then searches supported installation layouts. Settings shows:

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
- **Inspect & edit** creates an editable workspace without touching imported source.
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

- original UMML editor and loader tools behind process guards;
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

Upstream extractor code and binaries are not bundled when their repository does not declare a compatible project-wide license. See [UmaExtractor integration](docs/UMAEXTRACTOR_INTEGRATION.md).

### Settings

Settings manages installation selection, automatic detection, Manager data and workspace locations, Light/Dark/System appearance, diagnostics, metadata identity, and tester evidence.

Use **Create support bundle** to save a privacy-scrubbed ZIP for a bug or test report. It includes build/platform information, configuration-presence flags, high-level library/profile summaries, and read-only diagnostics. It excludes game assets, mod payloads, baselines, transaction contents, Veteran snapshots, raw settings, credentials, and known account identifiers.

Inspect `support-report.json` before uploading it. Custom package names or free-form errors may still contain text you consider private.

Manager-owned windows should open centered, raised, focused, and briefly topmost so new dialogs do not hide behind the main window like paperwork attempting escape.

## Player workflow

1. Launch Uma Mod Manager.
2. Confirm the detected installation in Settings.
3. Import a mod from Discover or a local package.
4. Wait for automatic preparation and source analysis to report **Ready**.
5. Enable the mod in a profile.
6. Configure package options when present.
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

See [Mod creator guide](docs/MOD_CREATOR_GUIDE.md) and [Manifest reference](docs/MANAGER_MOD_MANIFEST.md).

## Automatic preparation

Preparation is an internal background stage that converts creator-facing inputs into a verified deployable view. The user does not manage it manually.

Uma Mod Manager automatically queues newly imported compatible packages, stale metadata, older preparation layouts requiring migration, and source analysis that has not completed. Preparation never writes game files. Failure preserves the imported source and prior verified cache, continues the remaining queue, and reports a package-specific issue.

## Safety and recovery

Uma Mod Manager uses:

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

## Testing and feedback

Testing releases are for collecting evidence, not for converting strangers into an undocumented exception-handling system.

Before reporting:

1. Record the exact version, filename, and SHA-256.
2. Record OS, package format, game region, and native/Proton/Wine layout.
3. Write numbered reproduction steps.
4. State expected and actual results.
5. State whether game or Manager data changed.
6. Use **Settings → Create support bundle**, inspect it, and attach it when appropriate.
7. Link to third-party mods instead of uploading unauthorized copies.

Use the repository's structured **Testing feedback** issue form for pass, partial, and failure reports. The complete matrix and privacy guidance are in [Testing and feedback](docs/TESTING_AND_FEEDBACK.md).

## Command-line interface

The CLI and GUI use the same store, resolver, safety checks, and deployment engine.

```bash
umml-manager-cli --help
umml-manager-cli list
umml-manager-cli doctor
umml-manager-cli network-smoke
umml-manager-cli self-test
```

The legacy technical command name is intentional during the compatibility window. The CLI is not a back door around GUI blockers; it is deliberately equally paranoid.

## Further documentation

- [Alpha19 release notes](docs/releases/0.2.0-alpha.19.md)
- [Testing and feedback](docs/TESTING_AND_FEEDBACK.md)
- [Release process](docs/RELEASE_PROCESS.md)
- [Project vision](docs/PROJECT_VISION.md)
- [Branding and compatibility](docs/BRANDING_AND_COMPATIBILITY.md)
- [Mod creator guide](docs/MOD_CREATOR_GUIDE.md)
- [Architecture](docs/MANAGER_ARCHITECTURE.md)
- [Manifest reference](docs/MANAGER_MOD_MANIFEST.md)
- [Development](docs/MANAGER_DEVELOPMENT.md)
- [Packaging](docs/PACKAGING.md)
- [Security](SECURITY.md)
- [Release checklist](docs/MANAGER_RELEASE_CHECKLIST.md)
- [Third-party notices](NOTICE.md)

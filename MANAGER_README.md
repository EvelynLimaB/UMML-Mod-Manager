# Uma Mod Manager user guide

**Uma Mod Manager** is the primary desktop mod manager and creator workspace in this repository. It is a fork and continuation of UMML, with the original editor and loader functionality preserved through a guarded compatibility Studio while tested native workflows replace it piece by piece.

> **Community Test prerelease:** `0.2.0~alpha22`. The application includes bounded imports, immutable versions, provider browsing, automatic preparation and source analysis, profile-scoped configuration, visual package editing, the redesigned read-only Veteran Roster, verified deployment, recovery journals, installation detection, privacy-scrubbed support bundles, and native Linux/Windows packages.
>
> Alpha22 uses the browser-assisted GameBanana bridge as the supported interim fallback when GameBanana returns browser-only HTML instead of archive bytes. Official `uma-mod-manager:` one-click / Remote Install registration is planned separately.

Read the [alpha22 release notes](docs/releases/0.2.0-alpha.22.md) and [Testing and feedback](docs/TESTING_AND_FEEDBACK.md) before testing this build.

## Naming and compatibility

The public product and repository are named **Uma Mod Manager**. Existing technical identifiers remain unchanged during the migration so upgrades continue using the same data roots:

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

1. Download `umml-manager_0.2.0-alpha.22_win64.zip`.
2. Verify its SHA-256 against the release `SHA256SUMS`.
3. Extract the ZIP into its own folder.
4. Run:

```text
Uma Mod Manager.cmd
```

A compatibility launcher named `UMML Manager.cmd` remains during the migration window. No Python installation is required for the packaged build. Keep the previous extracted folder for rollback.

### Debian package

```bash
sudo apt install ./umml-manager_0.2.0~alpha22_amd64.deb
/usr/bin/umml-manager
```

The technical package name remains `umml-manager`, so alpha22 upgrades an earlier Manager package in place and continues using the same Manager data root.

### AppImage

```bash
chmod +x ./umml-manager_0.2.0-alpha.22_x86_64.AppImage
./umml-manager_0.2.0-alpha.22_x86_64.AppImage
```

The AppImage also exposes the CLI:

```bash
./umml-manager_0.2.0-alpha.22_x86_64.AppImage --version
./umml-manager_0.2.0-alpha.22_x86_64.AppImage --cli list
./umml-manager_0.2.0-alpha.22_x86_64.AppImage --cli doctor
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
- hydrated download totals rather than treating partial catalogue zeroes as confirmed zeroes;
- exact downloadable-file selection;
- bounded preview images;
- verified archive provenance;
- local Downloads/custom-folder scans;
- safe archive and local-folder validation.

Downloading and importing never deploys a mod.

#### GameBanana downloads in alpha22

The Manager first attempts a normal verified HTTPS transfer using GameBanana's file metadata. Some GameBanana `/dl/<file-id>` and `/mmdl/<file-id>` routes currently return an HTML landing or anti-abuse page instead of archive bytes.

When that specific browser-only response occurs, alpha22:

1. opens the selected GameBanana file URL in the user's real default browser;
2. watches the normal user/XDG Downloads directory;
3. ignores `.crdownload`, `.part`, `.download`, `.partial`, `.tmp`, old files, unrelated archives, and symlinks;
4. waits until the expected archive is stable and complete;
5. verifies expected byte size and MD5 when GameBanana's File API provides them;
6. imports the completed archive with the original GameBanana submission ID, file ID, source hash, and provider metadata.

On AppImage, the browser is launched through a sanitized host environment so Firefox/Chromium do not inherit PyInstaller's private library path.

The watched directory can be overridden for one launch:

```bash
UMML_GAMEBANANA_DOWNLOAD_DIR=/path/to/downloads \
  ./umml-manager_0.2.0-alpha.22_x86_64.AppImage
```

If the browser saves elsewhere, download the archive normally and import it through **Discover → Local folders**.

This browser-assisted bridge is an interim compatibility path. The intended long-term integration is GameBanana's registered manager protocol / Remote Install model, where the site passes the actual archive URL to `uma-mod-manager:`.

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

Legacy tools remain available until native replacements reach feature parity and pass restoration tests.

### Veteran Roster

Veteran Roster imports externally produced JSON from the `umadump` / `UmaExtractor` community family.

It can:

- import classic `data.json`;
- import Werseter `trained_chara_data.json`;
- reject support-card, trophy, friend, card, and replay outputs masquerading as rosters;
- remove known viewer/account identifiers and account-name fields recursively;
- store timestamped scrubbed snapshots with provenance and integrity hashes;
- enrich names, factor metadata, and exact factor stars from the installed `master.mdb` without modifying it;
- display evaluation ranks such as `S`, `S+`, `SS`, and higher tiers instead of raw score labels;
- display aptitude grades `G–S` instead of internal storage integers;
- show factor rarity as `1–3★` and skill acquisition as `Lv N`;
- search, sort, filter, build legacy shortlists, inspect, pin, compare, and export scrubbed records;
- resolve cached/local portraits and preload unique costume portraits without duplicating work for repeated runs;
- launch a user-selected external extractor in an isolated inbox.

Extractor `level: 0` factor values are treated as placeholders and fall back to the matching installed factor rarity. A skill's master-data rarity is not presented as its acquired level.

Cached artwork and portraits decoded from the installed game may appear automatically. Opening or scrolling the roster never starts a new artwork download. HTTPS fallback requires **Load portrait online** for the selected record or **Load all portraits online** for the roster. The artwork cache can be cleared without touching snapshots or game files.

Upstream extractor code and binaries are not bundled when their repository does not declare a compatible project-wide license. See [UmaExtractor integration](docs/UMAEXTRACTOR_INTEGRATION.md).

### Settings

Settings manages installation selection, automatic detection, Manager data and workspace locations, Light/Dark/System appearance, diagnostics, metadata identity, and tester evidence.

Use **Create support bundle** to save a privacy-scrubbed ZIP for a bug or test report. It includes build/platform information, configuration-presence flags, high-level library/profile summaries, and read-only diagnostics. It excludes game assets, mod payloads, baselines, transaction contents, Veteran snapshots, raw settings, credentials, and known account identifiers.

Inspect `support-report.json` before uploading it. Custom package names or free-form errors may still contain text you consider private.

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

## Automatic preparation

Preparation is an internal background stage that converts creator-facing inputs into a verified deployable view. The user does not manage it manually.

Uma Mod Manager automatically queues newly imported compatible packages, stale metadata, older preparation layouts requiring migration, and source analysis that has not completed. Preparation never writes game files. Failure preserves the imported source and prior verified cache, continues the remaining queue, and reports a package-specific issue.

## Standalone Werseter extractor host

Supported user-supplied Werseter source ZIPs use the packaged Python 3.14 runtime and `minidump 0.0.24` on Windows portable, Debian, and AppImage builds. A separate Python installation is not required for that supported workflow.

The Manager does not redistribute Werseter's source when the upstream repository lacks a compatible declared project-wide license. The user supplies the ZIP, and the extractor runs as a separate process under the current account.

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

Corrupt preferences are quarantined and reset with their original bytes preserved. Corrupt deployment, baseline, profile, library, recovery, or Veteran snapshot state blocks the affected operation rather than silently starting over.

## Testing and feedback

Testing releases are for collecting evidence.

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

The CLI is not a back door around GUI blockers; it deliberately uses the same safety boundaries.

## Further documentation

- [Alpha22 release notes](docs/releases/0.2.0-alpha.22.md)
- [Testing and feedback](docs/TESTING_AND_FEEDBACK.md)
- [GameBanana provider](docs/GAMEBANANA_PROVIDER.md)
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

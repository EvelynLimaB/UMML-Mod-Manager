# UMML Manager

UMML Manager is the full desktop manager and editing workspace for **Umamusume Pretty Derby** mods. It is packaged separately from legacy UMML while preserving the original loader's editing tools through a guarded compatibility Studio.

> **Preview:** `0.2.0~alpha15`. The manager includes bounded imports, immutable versions, provider browsing, automatic preparation, profiles, verified metadata provenance, fail-closed deployment, recovery journals, automatic installation detection, legacy-baseline migration, Studio compatibility, and matching DEB/AppImage packages. Real-game and destructive recovery testing remain required before a stable release.

## Install

### Debian package

```bash
sudo apt install ./umml-manager_0.2.0~alpha15_amd64.deb
/usr/bin/umml-manager
```

The package can coexist with `umml-linux`. It owns `/usr/lib/umml-manager`, `/usr/bin/umml-manager`, and `/usr/bin/umml-manager-cli` only.

### AppImage

```bash
chmod +x ./umml-manager_0.2.0-alpha15_x86_64.AppImage
./umml-manager_0.2.0-alpha15_x86_64.AppImage
```

The same file exposes the CLI:

```bash
./umml-manager_0.2.0-alpha15_x86_64.AppImage --version
./umml-manager_0.2.0-alpha15_x86_64.AppImage --cli list
./umml-manager_0.2.0-alpha15_x86_64.AppImage --cli browse --region global
```

Both formats use the same data directory:

```text
~/.local/share/umml-manager
```

CI builds both packages from one PyInstaller bundle, extracts the completed DEB and AppImage, compares their complete runtime trees, and verifies external checksums.

```bash
sha256sum -c SHA256SUMS
```

### Historical source-install cleanup

Early previews mixed application code with manager data. Do not use an old alpha1 `uninstall-manager.sh`, because it could delete that mixed directory.

Remove only stale alpha1 launchers while preserving the library and recovery state:

```bash
rm -f ~/.local/bin/umml-manager ~/.local/bin/umml-manager-cli
rm -f ~/.local/share/applications/io.github.evelynlimab.ummlmanager.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
hash -r
```

The current source installer stores the complete Manager and legacy Studio source runtime in `~/.local/share/umml-manager-app` and state in `~/.local/share/umml-manager`. It requires Tk and Pillow and reports when optional preparation/Studio dependencies are unavailable. Its source-specific launchers do not replace an installed Debian package.

## Interface

- **Library:** immutable versions, profiles, load order, preparation provenance, editable copies, and deployment.
- **Discover:** Global/Japan GameBanana browsing and bounded local package discovery.
- **Studio:** the complete legacy editor and loader interface behind process guards.
- **Conflicts:** exact file winners and every deployment blocker.
- **Settings:** installation detection, target paths, prepared metadata, diagnostics, manager data, and workspaces.

### Context-aware controls

Visible controls follow actual prerequisites instead of silently doing nothing:

- selection actions require a valid Library or local-discovery row;
- **Enable** changes to **Disable** for enabled mods;
- load-order arrows follow the selected mod's real position;
- **Prepare now** and **Re-prepare** reflect package and metadata state;
- **Apply profile** explains whether target data, metadata verification, blocker resolution, or closing the game is required;
- GameBanana paging and installation states survive background tasks;
- changed GameBanana search, sort, or region restarts on page 1;
- all Studio cards disable while the game runs;
- unknown process status blocks writes;
- operation controls disable while one manager task owns shared state.

Backend validation remains authoritative. Disabled-state logic improves the interface but does not replace locks, process checks, path validation, resolver blockers, or transaction safety.

## First run

1. Launch the game once and complete its data download.
2. Open UMML Manager. Detection may run while the game is open; deployment may not.
3. The manager detects Steam/Proton or DMM, validates paths, prepares `meta_decrypted_*.db`, records an installation key, and fingerprints the metadata.
4. When detection does not complete, use **Settings → Auto-detect installation**, then **Run diagnostics**.
5. Browse GameBanana or scan local folders from **Discover**.
6. Import a compatible package. Legacy UMML assets prepare automatically when readable metadata is available.
7. Enable prepared mods and arrange load order.
8. Inspect **Conflicts**. The plan must have zero blockers.
9. Close the game and apply explicitly.

Manual path changes clear verified installation identity and metadata fingerprints. Run auto-detection again before deploying enabled mods.

Enabling, disabling, and reordering mods never changes an existing profile binding. To intentionally move a profile to the currently detected installation, use **Settings → Bind profile here** and confirm the rebind.

If the old UMML already installed enabled assets, the first **Apply profile** checks the sibling `dat.backup` tree before taking ownership. When all needed originals are present, Manager offers to copy them into its protected, target-bound baseline and continue. It never moves or deletes the old backup. If any original is unavailable, no game file changes and the dialog directs you to legacy restore or Steam file verification.

The three target paths are:

- `.../Persistent/dat` for game asset files;
- UMML's prepared `meta_decrypted_*.db`, not the encrypted file named `meta`;
- the game installation directory containing its executable.

## Import, preparation, and deployment

The manager separates three operations:

1. **Import** preserves an immutable source version.
2. **Prepare** resolves source assets into hash-addressed targets using readable metadata.
3. **Apply** writes the enabled profile to the game through a verified transaction.

Import commits before automatic preparation. A preparation failure therefore preserves the downloaded archive and immutable source in Library with a retryable **Prepare now** action.

Prepared records retain file hashes, preparation time, and the metadata fingerprint used to build them. When current metadata is known, a missing or mismatched preparation fingerprint blocks deployment and requires re-preparation.

## Immutable library and concurrency

An imported ID/version is immutable. Re-importing the same identity with different bytes is rejected; re-importing identical bytes preserves the existing record and prepared cache; different versions coexist under safe storage components.

The public library boundary serializes the complete identity-selection, source-copy, and registry transaction. Threads in one process wait on a local mutex; separate manager processes use an advisory file lock. Concurrent imports therefore cannot select one record ID and leave a different source orphaned from the registry.

**Edit copy** creates a timestamped workspace with provenance. Change the edited package's ID or version before importing it as a new immutable version.

## GameBanana and loose legacy packages

Discover supports paging, search, sorting, authors, versions, statistics, file selection, original-page links, verified downloads, and bounded preview images.

Catalogue rows do not always contain full file lists. The manager offers **Install latest** while details load and replaces it with the real selector when available. Stale detail responses are ignored after selection or page changes.

Some older uploads contain loose files accepted by legacy UMML but omit a modern `assets/` wrapper or manifest. Compatibility normalization runs only when:

- strict import raises the typed unrecognized-package result;
- the archive came through the verified GameBanana provider path;
- recognizable UnityFS, audio, video, bundle, or hashed-asset evidence exists;
- no executable, script, or native-library payload exists.

Other storage, permission, or registry failures are not reinterpreted as legacy package layouts. Deep wrappers are handled through bounded, symlink-safe traversal.

Self-installing executables are not ordinary UMML asset packages. Manager rejects them and never runs downloaded mod code. UM:PD Dark Mode currently ships as a UABE self-installer, so supporting it requires a separate, exact-base patch backend; renaming or unpacking its EXE does not make it safe to deploy as hash-addressed assets.

Preview images are GameBanana-owned HTTPS content, load off the UI thread, use stale-selection tokens and a bounded session cache, and are limited by bytes and pixels. Preview failure remains nonfatal.

## Local discovery and archive safety

The scanner checks Downloads, Documents, Desktop, XDG user directories, and user-added roots. It is depth- and entry-limited and skips Steam libraries, Proton prefixes, VCS data, caches, dependency trees, hidden directories, and symbolic links.

Automatic detection requires recognizable evidence. Ordinary settings files and unrelated archives are not promoted to mods merely because their filenames look promising.

Imports reject traversal, absolute paths, drive prefixes, links, devices, FIFOs, sockets, duplicate archive paths, encrypted ZIP entries, excessive path lengths, more than 20,000 entries, and more than 8 GiB declared or actual extraction.

Hachimi packages may be discovered and preserved, but remain deployment blockers until a native Hachimi backend exists.

## Profiles and planning

Profiles are ordered lists; later mods win overlapping paths. Profiles retain target region and installation identity.

The resolver blocks:

- missing or unprepared mods;
- stale or unverified prepared caches;
- unsupported backends;
- wrong-region mods;
- wrong or unverified installation identity for a bound profile;
- invalid paths or hashes;
- missing declared dependencies;
- declared incompatibilities.

Duplicate profile entries are removed and reported instead of creating self-conflicts.

## Fail-closed deployment

GUI, CLI, and compatibility imports resolve to the same public deployment boundary. It rejects every resolver blocker before entering the transaction core.

Before mutation, the engine:

- acquires a cross-process deployment lock;
- verifies process inspection succeeded and the game is closed before recovery;
- rechecks immediately before restoring any interrupted transaction;
- verifies target installation identity;
- verifies prepared source hashes;
- validates contained target paths;
- verifies active state and external changes;
- snapshots affected targets with integrity records.

After snapshotting, deployment checks the game again, verifies active ownership against the snapshots, and confirms the live targets still match those snapshots before mutation starts. Deployment then uses atomic replacement, verifies installed files, captures untouched vanilla files once, writes target-scoped ownership state, and rolls back failed transactions.

An empty profile may restore managed paths from verified baselines without metadata. Enabled mods require verified metadata provenance. A matching pre-existing modded file is not adopted without a known vanilla baseline. When relevant legacy originals exist, an explicitly approved first-run migration preflights the complete set, copies them into Manager-owned baselines with integrity and provenance records, and leaves `dat.backup` untouched. Explicit force recovery may override a pre-existing active-state mismatch, but it never overrides a target change detected after recovery snapshots were captured.

Unreadable, future-version, wrong-target, malformed, or tampered critical state fails closed. Corrupt preferences are quarantined and reset because losing a preference is not equivalent to guessing file ownership.

## Diagnostics

**Run diagnostics** verifies more than stored strings. It reports:

- installation detection and writable paths;
- HTTPS trust source;
- settings, mod, and profile registries;
- installation identity;
- actual `dat`, game, and metadata path existence;
- metadata fingerprint integrity;
- interrupted transaction directories;
- active deployment state;
- process-inspection readiness and whether the game is running.

A failed process check is reported as failed and blocks writes. It is never converted into “game closed.”

## Legacy Studio

Every Studio card launches the same compatibility host, which can mutate game data. The entire Studio therefore requires the game closed. Individual callbacks retain guards, and the host watches for Umamusume throughout its lifetime.

Native Studio pages may replace legacy editors incrementally, but the compatibility host remains until every feature has a tested equivalent and restoration coverage.

## CLI

```bash
umml-manager-cli list
umml-manager-cli self-test
umml-manager-cli doctor
umml-manager-cli network-smoke --region global
umml-manager-cli verify-profile Default
umml-manager-cli scan ~/Downloads
umml-manager-cli browse --region global --sort updated
umml-manager-cli workspace creator.mod
umml-manager-cli prepare creator.mod --meta /path/to/meta_decrypted.db
umml-manager-cli profile Default creator.mod another.mod \
  --region global --installation-key steam-global
umml-manager-cli plan Default \
  --region global --installation-key steam-global \
  --meta /path/to/meta_decrypted.db
umml-manager-cli apply Default \
  --dat /path/to/Persistent/dat \
  --game-dir /path/to/game \
  --region global --installation-key steam-global \
  --meta /path/to/meta_decrypted.db
```

CLI apply requires explicit metadata or a saved metadata path whose actual hash still matches a recorded fingerprint. A saved path without a fingerprint is unverified and requires explicit `--meta` or installation auto-detection. A saved installation key is reused only when the requested `dat` path matches the saved target.

The GUI prompts before legacy-baseline migration. CLI callers must make the same decision explicitly by adding `--import-legacy-baselines` to `apply`.

`self-test` uses synthetic temporary files. `doctor` inspects the saved target and Manager state without repairing or changing it. `network-smoke` checks current GameBanana catalogue, detail, file metadata, and preview decoding without downloading a mod. `verify-profile` reads a real prepared profile but performs its apply, legacy-baseline migration, and restoration only on temporary copies; it also rechecks the live target hashes before reporting success.

For AppImage use, prefix CLI arguments with the AppImage filename and `--cli`.

## Development and packaging

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-build.txt
python -m pip check
python scripts/audit_manager.py
bash scripts/check_manager.sh
bash scripts/build_manager_frozen.sh
bash scripts/build_manager_deb.sh
bash scripts/build_manager_appimage.sh
```

CI compiles every manager file, audits architecture and dangerous calls, runs adversarial and failure-injection tests, validates desktop/AppStream metadata, builds one frozen runtime, compares complete DEB/AppImage payloads, checks certifi and Pillow, and verifies external checksums.

Read `CONTRIBUTING.md`, `docs/MANAGER_ARCHITECTURE.md`, `docs/MANAGER_DEVELOPMENT.md`, `docs/MANAGER_AUDIT.md`, `docs/MANAGER_FEATURE_ROADMAP.md`, `docs/MANAGER_MAIN_PROMOTION.md`, and `docs/PACKAGING.md` before changing state, providers, deployment, recovery, or packaging.

## Remaining alpha release gates

- live Bazzite GameBanana browse, preview, detail hydration, deep loose-package normalization, automatic preparation, and import without certificate overrides;
- real-desktop state and diagnostics smoke testing across every page;
- a broader current-mod corpus;
- packaged apply/disable/restore/update tests on disposable game data;
- deliberate process-kill recovery drills at transaction boundaries;
- explicit multi-installation target UI and separately scoped state directories;
- native Hachimi deployment;
- native Studio service extraction and generated local mods;
- exact-build runtime/in-game integration as a separate optional component.

## Safety

- Keep the game closed during apply, restore, database editing, and all legacy Studio use.
- Treat archives, provider responses, manifests, manager state, and recovery material as untrusted input.
- Do not delete interrupted transaction directories until diagnostics or recovery explains them.
- Do not commit game files, decrypted metadata, downloaded archives, manager state, or user paths.
- Modding may violate the game's terms of service.

UMML Manager code is MIT-licensed. Imported mods retain their own licenses.

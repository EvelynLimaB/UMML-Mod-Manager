# UMML Manager changelog

## 0.2.0~alpha15 - 2026-07-26

### Manager installation detection

- Fixed the Manager GUI, CLI doctor, source install, DEB, and AppImage entry points using the older `umml_platform` discovery path even though the robust Steam/Proton detector was packaged.
- Manager installation retries now perform a fresh robust scan instead of retaining a failed first-run result.
- Manager diagnostics now produce one consistent readiness verdict with scored Steam roots, libraries, game candidates, Proton data candidates, selected paths, and actionable incomplete-discovery notes.
- Added regressions for replacing a legacy Linux detection miss, refreshing after game data becomes available, and exposing robust discovery evidence through diagnostics.
- Source, frozen, extracted DEB, installed DEB, and AppImage runtimes now have to detect a disposable native Mint/Debian Steam layout that the older Manager path missed.

## 0.2.0~alpha14 - 2026-07-25

### Main-promotion verification

- Added a package-level disposable self-test covering folder and ZIP imports, conflict winners, profile switching, exact restoration, external-change refusal, legacy-baseline migration, and interrupted-transaction recovery.
- Added a read-only `doctor` command for platform detection, HTTPS trust, target identity, metadata integrity, registry, transaction, active-state, and baseline checks.
- Added a live GameBanana metadata/detail/preview smoke test that never installs a download or writes to the game.
- Added a real-profile verifier that reads the selected profile and prepared payloads, copies only affected targets and trusted baselines into temporary storage, applies and restores there, and confirms the live target files remain unchanged.
- Added a native Tk smoke mode that constructs and renders Library, Discover, Studio, Conflicts, and Settings against disposable data.
- Added one Bazzite-ready promotion script that records package identity and runs all of these checks without deploying to the live game.

### Packaging and branch protection

- The Manager workflow now runs on pushes to `main`, not only on feature branches.
- CI exercises source install/upgrade/uninstall preservation, every frozen GUI page under Xvfb, the AppImage and extracted DEB runtimes, and a real Debian package install/remove cycle that preserves user data.
- Frozen, DEB, and AppImage entry points run the same disposable deployment self-test.
- The promotion policy now separates the requirements for merging this alpha preview into `main` from the larger real-game and destructive test matrix required for a stable Manager release.

## 0.2.0~alpha13 - 2026-07-23

### Legacy takeover and baseline safety

- First apply now recognizes relevant originals in legacy UMML's sibling `dat.backup` tree and offers one explicit migration step instead of an opaque asset-hash failure.
- Migration preflights the complete required set, copies originals into Manager-owned target-bound baselines, records hash and legacy provenance, and never moves or deletes the old backups.
- Files carrying a different legacy mod can no longer be silently captured as vanilla merely because they differ from the newly requested winner.
- Missing, unreadable, or incomplete legacy originals stop before game mutation or partial baseline import and produce a short legacy-restore/Steam-verification action.
- A verified existing baseline now permits deliberate adoption of an already matching target; normal first adoption without a baseline still fails closed.
- CLI callers can opt in with `apply --import-legacy-baselines`.

### Compatibility and tests

- Documented that UM:PD Dark Mode is a self-installing UABE patch, not a generic hash-addressed asset package; downloaded executable content remains rejected and is never run.
- Added regressions for matching and nonmatching legacy mods, untouched originals, all-or-nothing migration, backup preservation, exact restoration, existing-baseline adoption, and concise GUI recovery prompts.

## 0.2.0~alpha12 - 2026-07-23

### Transaction and recovery safety

- Recovery now verifies that process inspection works and the game is closed before restoring an interrupted transaction, then checks again immediately before rollback.
- Apply revalidates active ownership against captured snapshots and verifies the live targets still match those snapshots immediately before mutation begins.
- External changes made while a transaction is being prepared are preserved and reported, including when explicit force recovery was requested.
- A pre-existing file that already matches a requested mod is no longer adopted as manager-owned unless a valid vanilla baseline already exists.

### Installation and profile identity

- CLI apply no longer treats a saved metadata path without a recorded fingerprint as implicitly verified; explicit `--meta` or a fresh auto-detection is required.
- Auto-detection uses an explicit one-shot save authorization, so typing a path after detection cannot retain stale installation identity merely because the status text still says “Detected”.
- Enabling, disabling, and reordering mods preserve a profile's existing region and installation binding.
- Settings now exposes an explicit **Bind profile here** action for intentional profile rebinding to a verified installation.

### Library and source installation

- Re-importing an identical immutable ID/version returns the existing record without discarding prepared files or metadata provenance.
- The source installer now carries `UMML.py`, `UMML_core.py`, `UMML_data`, `umml_platform.py`, and `umml_autodetect` alongside the manager package.
- Source installation requires Pillow for the graphical manager, reports the `certifi` fallback state, and clearly distinguishes missing optional preparation/Studio dependencies.

### Tests

- Added regressions for recovery ordering, process-inspection failure, snapshot races, unsafe first adoption, unverified saved metadata, post-detection manual edits, profile-binding preservation, idempotent re-import, and complete source-install payloads.

## 0.2.0~alpha11 - 2026-07-23

### Deployment safety

- Added one public deployment boundary for GUI, CLI, package-level, and compatibility callers.
- The backend now rejects every resolver blocker, including stale preparation caches and wrong or unverified installation identity.
- Process-inspection failures block writes instead of being interpreted as proof that the game is closed.
- CLI apply now requires explicit metadata or a saved metadata database whose actual hash still matches the recorded fingerprint.
- Bound profiles no longer deploy when the target installation identity is missing.
- Prepared caches with no metadata provenance are treated as unverified when current metadata is known.

### Library and provider safety

- Immutable import identity selection, source copying, and registry updates are serialized across threads and processes.
- Added a typed unrecognized-package exception so GameBanana compatibility normalization no longer matches human-readable error strings.
- Malformed source metadata now fails through the normal StoreError boundary instead of leaking an AttributeError.
- Plain GameBanana game names map to the original Japanese listing; the Global listing still requires its explicit marker.

### Interface and diagnostics

- Library rows distinguish prepared, stale, and unverified preparation state.
- Enabled profiles require verified metadata before Apply becomes available; an empty profile may still restore managed files from verified baselines.
- Diagnostics now verify actual target-path existence, metadata fingerprint integrity, and process-inspection readiness.
- The full legacy Studio is marked as game-data capable and remains disabled while the game runs.

### Maintenance and tests

- Documented the guarded `library.py` and `deployment.py` public boundaries above the mature storage and transaction cores.
- Added real-class regressions for blocker enforcement, process-backend failures, malformed state, typed provider fallback, installation scoping, metadata verification, compatibility aliases, and concurrent imports.
- Kept the public compatibility bridges reload-safe while historical raw imports are migrated incrementally.

## 0.2.0~alpha10 - 2026-07-23

### Import compatibility

- Normalized legacy GameBanana packages are no longer rejected merely because their first regular asset is nested more than four directories below `assets/`.
- Mod-root recognition now uses a bounded, symlink-safe breadth-first traversal with explicit entry and depth limits instead of an arbitrary four-component shortcut.
- Deep wrapper layouts accepted by the legacy UMML manual loader can now continue from normalization into immutable import and automatic preparation.

### Interface controls

- Library selection controls now disable until a valid row is selected, and **Enable**, load-order arrows, **Prepare now**, **Re-prepare**, and **Apply profile** reflect the selected mod and profile state.
- Apply explains whether the game must close, blockers must be fixed, or the game data path must be configured instead of remaining as an apparently dead button.
- GameBanana install and paging controls preserve their semantic state across background tasks; changed region, sort, or query starts again on page 1.
- Local discovery open/import buttons follow the selected candidate and report invalid calls instead of silently returning.
- Every operation that owns shared manager state disables competing actions until completion or failure.
- The full legacy Studio and every direct Studio tool are disabled while the game runs because they all share the same compatibility host and lifetime watcher.
- Unknown game-process status now blocks Apply and legacy Studio writes instead of being interpreted as game closed.
- Directly typed target paths or region changes clear stale installation identity and metadata fingerprints when settings are saved; a completed auto-detection preserves its newly verified values.
- Browser and folder launch failures now produce visible feedback rather than disappearing into a failed desktop subprocess.

### Tests and audit

- Added a regression archive whose UnityFS payload remains deeply nested after the compatibility normalizer unwraps its first four wrapper directories.
- Added a static audit that verifies every visible Tk button callback resolves to the manager or an action mixin.
- Added headless state regressions for selection, busy tasks, paging, blockers, GameBanana search reset, game-running and unknown-status safety, full Studio behavior, and typed Settings edits.
- Retained executable-content rejection, document-only rejection, automatic-preparation policy, offline-CLI, structural-audit, and package-parity coverage.

## 0.2.0~alpha9 - 2026-07-22

### Import and preparation

- Compatible legacy UMML asset packages are prepared automatically immediately after import when the detected metadata database is available.
- A failed preparation no longer discards the downloaded or imported source; the mod remains safely in Library and can be retried with **Prepare now**.
- Applying a profile remains a separate explicit action and still requires the game to be closed.
- Provider-confirmed GameBanana archives that contain valid loose UnityFS/audio/video/hash payloads but omit the modern `assets/` wrapper are normalized into an immutable UMML package automatically.

### Safety

- Loose-archive normalization is limited to the GameBanana provider path and requires recognizable game-asset evidence.
- Archives containing executable, script, or native-library payloads are rejected instead of being wrapped as ordinary assets.
- Plain documents and unrelated ZIP files remain unrecognized rather than being imported optimistically.

### Tests

- Added integration coverage for the loose legacy archive shape seen in existing UM:PD GameBanana uploads.
- Added rejection tests for document-only and executable-bearing archives.
- Added policy tests for automatic preparation eligibility.

## 0.2.0~alpha8 - 2026-07-22

### Fixed

- Selecting a GameBanana catalogue row no longer leaves **Install** disabled merely because the index response omitted full downloadable-file metadata.
- The selected submission now fetches its detail record in a dedicated background task and replaces the fallback with the actual file selector when available.
- **Install latest** remains usable while details are loading or when prefetch fails; installation retries the detail endpoint instead of treating an incomplete catalogue row as a submission with no files.
- Stale detail responses are discarded after selection changes, page changes, or shutdown.
- GameBanana file containers are normalized from arrays, numeric-keyed objects, and nested containers before file selection.
- The interactive install path now uses the same preview-aware provider used by browsing and the provider registry.

### Tests

- Added regression coverage for mapping-shaped and nested GameBanana file containers.
- Retained the dependency-complete manager suite, structural audit, package parity checks, and legacy validation.

## 0.2.0~alpha7 - 2026-07-22

### Triple-audit corrections

- Manager regression CI now installs the complete pinned runtime dependency set before running tests, so Pillow-backed preview tests cannot silently skip in the manager workflow.
- The default provider registry now registers the preview-aware GameBanana client instead of the legacy metadata-only client.
- Provider integration tests verify that real GameBanana media fields are normalized through the registered client, not merely through an isolated helper.
- Package inspection now checks for Pillow's compiled imaging extension in both the DEB and AppImage as well as the existing full-runtime parity comparison.
- Dependency installation is followed by `pip check` in both test and packaging jobs.

### Documentation and release preparation

- Preview images are recorded as implemented; persistent offline image caching and before/after comparison remain roadmap items.
- The release checklist now distinguishes completed region/dependency planning support from missing GUI and automatic-install workflows.
- Alpha7 is a distinct package version so corrected artifacts cannot be confused with the previously distributed alpha6 binary.

## 0.2.0~alpha6 - 2026-07-22

### Audit and verification

- Added a standard-library AST audit for syntax, duplicate definitions, mutable defaults, bare exceptions, dangerous deserialization/extraction calls, `shell=True`, and core-layer import violations.
- Expanded regression coverage with adversarial path, archive, immutable-source, provider, schema, baseline, recovery-snapshot, metadata-freshness, installation-binding, and failure-injection tests.
- CI now separates compile, architecture audit, regression tests, metadata validation, frozen builds, package inspection, and full DEB/AppImage runtime-tree parity.
- Failed regression runs upload their complete test log instead of leaving the useful traceback buried under runner setup output.

### Deployment and recovery

- Managed manifest, active-state, baseline, and recovery-journal paths are normalized and required to remain under their declared roots.
- Prepared files are SHA-256 verified before deployment, and installed targets are verified after atomic replacement.
- Active state and vanilla baselines are bound to a specific canonical `Persistent/dat` target so another installation cannot reuse them accidentally.
- Deployment uses cross-process locks and durable transaction journals with snapshot, apply, and commit phases.
- Interrupted transactions are recovered before another profile is applied; unreadable or tampered recovery material fails closed.
- Recovery snapshots and vanilla baseline files now have independent SHA-256 integrity records.
- Snapshot failures before mutation clean up without pretending a rollback failed.
- Future active-state, registry, profile, journal, and baseline schema versions are rejected explicitly.

### Imports, providers, and preparation

- Local folder imports reject symbolic links and special files, enforce file/byte limits, and verify the copied tree still matches the pre-copy digest.
- Mod version text no longer directly controls filesystem paths; display versions and safe storage components are separate.
- Automatic discovery no longer treats every ZIP or ordinary `setting.json` as a mod.
- Ambiguous wrapper folders are rejected rather than selecting one nested package arbitrarily.
- Preparation is staged transactionally and preserves the last working prepared cache until the replacement and registry update both succeed.
- Prepared records store the metadata database fingerprint and preparation time.
- GameBanana downloads use immutable per-submission/per-file locations, temporary partial files, HTTPS redirect validation, JSON/download size limits, and exact archive provenance.
- Remote GameBanana metadata is applied before selecting the immutable source path, keeping the record version and storage version consistent.

### Profiles and future feature boundaries

- Profiles now retain region, installation identity, and per-mod option space.
- Plans block wrong-region mods, wrong-installation profiles, unsupported package backends, stale prepared caches, missing dependencies, declared incompatibilities, invalid manifests, missing mods, and unprepared mods.
- Duplicate profile entries are deduplicated and reported instead of creating self-conflicts.
- Added explicit provider and deployment-backend contracts.
- Hachimi packages remain discoverable and preservable, but are clearly blocked until a separately tested runtime backend exists.
- Added a phased feature roadmap covering multi-install targets, provider-neutral downloads, staged updates, deployment backends, native Studio tools, and the optional runtime bridge.

### GUI and Studio

- Selected GameBanana mods now display their parsed preview image above the description and file selector.
- Preview loading is asynchronous, selection-tokened, session-cached, verified HTTPS-only, limited to 12 MiB and 40 megapixels, and non-blocking when an image is unavailable.
- Pillow raster codecs are included in both frozen package formats so JPEG, PNG, GIF, and WebP previews render consistently.
- Background task callbacks are discarded after GUI shutdown instead of calling a destroyed Tcl interpreter.
- Corrupt settings are quarantined with their original bytes preserved, then reset to defaults with a diagnostics warning.
- Installation detection stores an installation key and prepared-metadata fingerprint; manual path edits deliberately clear verified identity.
- The legacy Studio host watches the game for its full lifetime and closes when Umamusume starts.

## 0.2.0~alpha5 - 2026-07-22

### Fixed

- GameBanana HTTPS now resolves the target system's certificate trust store instead of relying on OpenSSL paths inherited from the Ubuntu build runner.
- Fedora, Bazzite, RHEL, Debian, Ubuntu, Mint, Alpine, SUSE, and common BSD-style CA bundle locations are recognized.
- `SSL_CERT_FILE` and `SSL_CERT_DIR` are honored and validated explicitly.
- A bundled `certifi` Mozilla CA bundle provides a portable fallback when the target system path cannot be resolved.
- GameBanana certificate failures now report the selected trust source and never recommend disabling verification.

### Diagnostics and packaging

- Manager diagnostics now report whether HTTPS certificate verification is ready and which CA file or directory is selected.
- Dedicated TLS tests cover Fedora/Bazzite path fallback, invalid explicit environment paths, SSL context construction, diagnostics, and actionable GameBanana errors.
- The frozen DEB and AppImage are both inspected for the bundled `certifi/cacert.pem` file.
- Complete frozen-runtime parity checks between the source bundle, DEB, and AppImage remain required.

## 0.2.0~alpha4 - 2026-07-22

### Added

- A separate x86_64 AppImage built from the exact same frozen manager runtime as the Debian package.
- AppImage desktop integration metadata, icon, AppStream metadata, GUI entry point, CLI mode, and legacy Studio host.
- CI artifacts for the DEB, AppImage, and a shared external `SHA256SUMS` file.
- AppImage smoke tests for version reporting and CLI startup.
- AppImage extraction checks that compare the embedded manager executable byte-for-byte with the frozen bundle used by the DEB.

### Safety

- ZIP and TAR imports now enforce a 20,000-entry and 8 GiB expanded-size limit before extraction.
- Encrypted ZIP entries and archive special files are rejected.
- Archive member names have a bounded length.
- Temporary imports continue to be removed on every failure path.
- `appimagetool` is downloaded over HTTPS and checked against a pinned SHA-256 before use.

### Packaging

- The Debian and AppImage packages are inspected in the same CI job after one shared PyInstaller build.
- Checksums are generated outside the packages to avoid self-referential package hashes.
- The AppImage can be invoked as a GUI application, with `--version`, or with `--cli` for manager CLI commands.

## 0.2.0~alpha3 - 2026-07-21

### Fixed

- Debian desktop launches now use `/usr/bin/umml-manager` directly so stale user-level PATH entries cannot silently start an older source copy.
- Source application files now live in `~/.local/share/umml-manager-app`; manager library and deployment state remain separately preserved in `~/.local/share/umml-manager`.
- The source installer uses a distinct desktop ID and source-specific launchers. Its compatibility commands prefer the Debian package whenever installed.
- The source uninstaller no longer deletes the manager library, profiles, settings, baselines, transactions, downloads, or workspaces.
- Enabled but unprepared mods now block profile deployment instead of producing a misleading successful no-op.
- Corrupt `active.json`, mod registry, and profile registry files fail closed instead of being silently treated as empty state.
- Re-importing the same mod ID and version with different contents can no longer overwrite immutable source files.
- Different versions of the same logical mod coexist under distinct manager record IDs instead of replacing the registered version.
- GameBanana result changes now clear stale selections, disable invalid install actions, and honor previous/next page availability.

### Changed

- Conflict plans explicitly list missing and unprepared enabled mods.
- Workspace instructions require a new version or ID before importing edited content.
- GameBanana and local discovery tables now include vertical scrollbars.

## 0.2.0~alpha2 - 2026-07-21

### Fixed

- First launch now invokes the existing Steam, Proton, DMM, and regional installation detector instead of leaving every path field blank.
- Detected encrypted metadata is automatically converted into UMML's validated readable `meta_decrypted_*.db` cache.
- Saved paths are validated at startup and re-detected when missing or stale.
- Background-task error callbacks now capture exceptions safely instead of retaining a cleared Python exception variable.

### Changed

- Settings begins with a guided **Auto-detect installation** action and explains when manual paths are needed.
- Path labels now distinguish the game installation, `Persistent/dat`, and the prepared metadata database.
- Taiwan is retained as a selectable game region even though the GameBanana browser currently exposes Global and Japan catalogues.

## 0.2.0~alpha1 - 2026-07-21

### Added

- Polished dark sidebar interface with Library, Discover, Studio, Conflicts, and Settings workspaces.
- Built-in GameBanana browser for the separate Global and Japan Umamusume listings.
- GameBanana paging, search, sorting, descriptions, authors, versions, statistics, file selection, page links, download, and import.
- Bounded automatic detection of nested mod folders and compatible ZIP/TAR archives.
- Configurable scan roots with Downloads, Documents, and Desktop defaults.
- Editable workspace copies that retain provenance and never mutate immutable imported versions.
- Studio compatibility host containing the full legacy UMML workspace and direct launch cards for character attributes, personality, dresses, training, story concerts, model swaps, translation merge, cleanup, and database reset.
- Game-running guards around mutating legacy Studio actions.
- CLI commands: `scan`, `browse`, `workspace`, and `studio`.

### Changed

- Nested parent folders can now be selected directly; the importer resolves the actual mod root.
- GameBanana metadata records descriptions, version, categories, statistics, previews, and all listed files when available.
- The frozen manager package now bundles the legacy editor backend and modular interface pages.
- Manager version advanced from `0.1.0~alpha1` to `0.2.0~alpha1`.

### Safety

- Local scanning is depth- and entry-limited and skips Steam, Proton, VCS, cache, and dependency directories.
- Archive traversal, links, devices, and unsafe paths remain rejected.
- Studio writes remain blocked while Umamusume is detected.

## 0.1.0~alpha1 - 2026-07-21

- Initial separately packaged manager foundation.
- Immutable mod library and named ordered profiles.
- Deterministic conflict planning and transactional deployment.
- Vanilla baseline and external-change protection.
- Folder, ZIP, TAR, and direct GameBanana import.
- Tk GUI, CLI, tests, frozen runtime, and independent Debian package.

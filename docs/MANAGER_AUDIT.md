# UMML Manager code audit

Audit target: `agent/umml-manager-foundation`, manager `0.2.0~alpha15`.

This document began with the code-level audit performed after the first Bazzite AppImage test and now includes the alpha13 legacy-baseline migration, alpha14 main-promotion verification, and alpha15 Manager autodetection wiring follow-ups. It separates corrected defects from remaining release and architecture work. A green build is evidence for one revision, not a ceremonial declaration that bugs have become extinct.

## Method

The audit traced every manager-owned Python module and packaging entry point across these boundaries:

1. persisted models and schema migration;
2. local-folder and archive ingestion;
3. remote provider metadata and downloads;
4. preparation and immutable caches;
5. profile resolution and compatibility;
6. deployment, baselines, rollback, and crash recovery;
7. Steam/Proton installation and process detection;
8. legacy Studio subprocess boundaries;
9. Tk background tasks and shutdown;
10. PyInstaller, DEB, AppImage, CI, and documentation parity.

The repository now also runs `scripts/audit_manager.py`, a standard-library AST audit covering syntax, duplicate definitions, mutable defaults, bare exceptions, dangerous deserialization/extraction calls, `shell=True`, and core-layer import violations.

## Corrected critical findings

### Managed paths could escape the game data directory

Prepared manifests and active state were concatenated with `Persistent/dat` without canonical validation. A malicious or corrupted registry path such as `../outside` could therefore target a parent directory.

Correction:

- every managed path is normalized as a POSIX relative path;
- absolute paths, drive prefixes, empty segments, `.` and `..` are rejected;
- target parents are resolved and required to remain beneath the declared root;
- symbolic-link targets are rejected;
- active state and recovery journals are revalidated before use.

### Prepared hashes were not verified before deployment

The resolver recorded SHA-256 values, but deployment copied the prepared file without confirming that it still matched. A modified prepared cache could therefore bypass the profile plan.

Correction:

- the complete winning prepared set is verified before any snapshot or game-file write;
- missing or changed files block deployment with the affected mod and path;
- active-state hashes are validated as real SHA-256 values.

### Deployment state and vanilla baselines could be reused on another installation

The original state described files but not the game installation that owned them. Reusing one manager data root for another Steam library, region, or installation could restore the wrong baseline.

Correction:

- deployment state and baseline manifests include a target ID derived from the canonical `Persistent/dat` path;
- mismatched targets fail closed;
- legacy state is migrated only when the saved installation path matches;
- a future multi-target registry must use separately scoped active state and baselines rather than relaxing this check.

### A process crash had no durable recovery protocol

The old transaction directory was removed on handled exceptions, but an OS crash or killed process could stop between file writes and active-state commit.

Correction:

- snapshots and a durable JSON journal are written before mutation;
- journal phases distinguish snapshot setup, applying, and committed state;
- the active-state document records the committing transaction ID;
- a later apply recovers or finalizes interrupted transactions before creating a new one;
- unreadable recovery material blocks further deployment instead of being deleted.

### Recovery could restore files before checking the game process

Interrupted `applying` or `committed` journals were rolled back before process inspection. A running game or failed process backend could therefore still be followed by manager-owned file writes.

Correction:

- apply checks process state before entering recovery;
- recovery checks again immediately before each rollback;
- a running game or inspection failure preserves both target bytes and recovery material;
- tests cover a process starting and process inspection failing between the outer check and rollback.

### Targets could change between verification and mutation

Active files were checked before transaction setup, but snapshots were captured later and then trusted. Another tool could change a target in that window and have its change overwritten.

Correction:

- captured snapshot hashes are compared with the active ownership manifest unless explicit force recovery was requested;
- live targets are compared with every snapshot after the final process check and immediately before mutation begins;
- a post-snapshot change blocks even force recovery and is preserved without rollback;
- an already matching unmanaged mod file is not adopted when no vanilla baseline exists.

### First Manager apply could not safely take over legacy UMML files

The first safe-adoption guard correctly refused a file that already matched a requested mod, but exposed only an opaque asset hash and a dead-end “explicit recovery workflow.” Worse, a different legacy-installed mod could be mistaken for untouched vanilla because it did not match the new winner.

Correction:

- every first-touch profile path is compared with the corresponding sibling legacy `dat.backup` entry;
- differing legacy-managed targets use the saved original instead of being captured as vanilla;
- the complete required migration set is preflighted and copied into Manager-owned, target-bound baselines only after explicit confirmation;
- legacy backups are hash-verified after copy, retain provenance, and are never moved, deleted, or used to replace an existing Manager baseline;
- missing originals leave both game files and Manager baselines unchanged and produce a short restore/Steam-verification action instead of an opaque hash dump;
- CLI migration requires `--import-legacy-baselines`.

## Corrected high-severity findings

### Preparation deleted the previous working cache first

A failed metadata lookup could leave a previously prepared mod unusable.

Correction:

- decode and normalization happen in a staging directory;
- duplicate output hashes and empty output fail before commit;
- the old cache moves aside only after the new cache is complete;
- registry failure restores the previous cache;
- prepared records store metadata SHA-256 and preparation time.

### Local-folder imports accepted symbolic links and special files

`copytree` could follow local links outside the selected mod tree.

Correction:

- imports inspect entries without following links;
- symlinks, devices, sockets, FIFOs, and other special files are rejected;
- file-count and byte limits are enforced for extracted folders as well as archives.

### Imported version text influenced filesystem paths

A package version was used directly as a directory component.

Correction:

- display versions remain unchanged in metadata;
- storage components are sanitized and receive a digest suffix when transformation is needed;
- immutable source and prepared paths are generated by the store, not by providers.

### Failed provider downloads could destroy a previous archive

GameBanana downloads opened their final filename directly. A repeated failed download could truncate and then remove an older file with the same name.

Correction:

- downloads use per-submission/per-file directories and temporary `.part` files;
- final replacement happens only after a complete verified transfer;
- declared and actual sizes are bounded;
- source SHA-256, filename, byte size, and fetch time are recorded;
- final redirects must remain HTTPS.

### GameBanana version metadata could disagree with immutable storage

The archive was imported using local metadata, after which the record version was changed to the remote display version. The source path and registry could describe different versions.

Correction:

- provider metadata overrides are applied before the immutable destination is selected;
- GameBanana records use a stable submission-based ID;
- remote version, author, description, and region provenance are stored as one import transaction.

## Corrected medium-severity findings

- Duplicate profile IDs are deduplicated and reported instead of creating self-conflicts.
- Profile planning now reports unsupported package backends, wrong regions, missing dependencies, declared incompatibilities, invalid manifests, missing mods, and unprepared mods.
- Hachimi folders remain discoverable but cannot masquerade as deployable legacy assets.
- Discovery counts inspected child entries, skips symlinks, reads XDG user directories, and requires stronger metadata evidence.
- GameBanana primary and fallback failures retain both error contexts instead of returning an unexplained empty catalogue.
- JSON responses and downloads have explicit size limits.
- GUI background callbacks are discarded after shutdown instead of calling a destroyed Tcl interpreter.
- Diagnostics validate manager registries and report interrupted deployment directories.
- The legacy Studio host monitors the game for its entire lifetime and closes when Umamusume starts.
- Profile names cannot silently overwrite an existing profile through the New Profile dialog.
- Mod and profile registries use cross-process advisory locks, atomic writes, and previous-file backups.

## New feature boundaries

### Package and backend capabilities

Records now declare:

- package type;
- capabilities;
- dependencies;
- incompatibilities;
- supported regions;
- preparation metadata.

`umml_manager.backends` declares the currently available legacy asset backend, the planned Hachimi backend, and unsupported packages. Detection and deployment are intentionally separate concepts.

### Provider contracts

`umml_manager.providers.base` defines provider descriptors, browse/update capabilities, and a registry. Providers own remote metadata, downloads, and provenance. They do not prepare assets, resolve profiles, or write into the game.

### Profile expansion

Profiles now have schema space for:

- target region;
- installation key;
- per-mod options.

The current UI enforces installation keys for bound profiles. Membership and load-order edits preserve existing bindings, while **Bind profile here** performs an explicit verified-target rebind. Per-mod options remain reserved for the generated-mod work described in the feature roadmap.

## Remaining risks and release blockers

### Multi-installation state is safe but not yet convenient

The manager now refuses to reuse active state or a baseline on another target. It does not yet maintain a first-class target registry with separately selectable Global/Japan installations. This is fail-closed, but the UX is incomplete.

### Legacy Studio still contains old mixed UI/business logic

The subprocess boundary and lifetime watcher reduce risk, but native Studio pages must eventually call headless services with operation-level game checks and generated patch output. The watcher interval cannot eliminate every sub-second process-start race inside old nested callbacks.

### Provider authenticity stops at transport and hashing

TLS, immutable archives, provenance, and SHA-256 protect transfer and later mutation. They do not prove a third-party author signed a package. A future manifest-signature system must be optional and must not imply that unsigned historical mods are malicious.

### Remote behavior needs real corpus testing

GameBanana response compatibility, redirects, archive names, very large downloads, obsolete submissions, multiple files, and interrupted transfers require packaged tests against current real submissions.

### Metadata/game-update rebasing needs a user workflow

Prepared records store the metadata database hash and the UI exposes stale/unverified state. It still needs a bulk re-prepare operation and explicit baseline refresh/rebase flow after verified game updates.

### Recovery needs destructive real-machine drills

Unit tests cover journal phases and rollback behavior. Release validation must still kill the packaged manager at controlled points while operating on a disposable synthetic game tree, then exercise recovery from both DEB and AppImage builds.

### Windows remains a separate packaging target

Process and path code retain Windows branches, but alpha6 packages are Linux x86_64. Windows frozen packaging and native tests are not implied by Linux CI.

## Audit acceptance gates

A release candidate should not be promoted until:

- the structural audit and all manager tests pass;
- DEB/AppImage runtime trees match the shared frozen bundle;
- the packaged Bazzite GameBanana workflow succeeds without overrides;
- at least one real mod is prepared, applied, disabled, restored, updated, and rolled back;
- an interrupted apply is recovered on a disposable tree;
- a game update stale-cache and baseline scenario is rehearsed;
- source/DEB/AppImage coexistence preserves one library and does not shadow launchers;
- every remaining blocker is either completed or explicitly excluded from the advertised feature set.

# UMML Manager architecture

UMML Manager is intentionally separate from the legacy one-folder loader. The legacy application performs direct, imperative mod operations; the manager owns a persistent library and computes a complete desired game state from profiles.

## Component boundary

```text
Provider / local import
        │
        ▼
Public library boundary (library.py)
        │  ├── typed package recognition
        │  ├── same-process import mutex
        │  └── cross-process import lock
        ▼
Immutable source library (store.py core)
        │
        ▼
Preparation cache ────── readable metadata DB + fingerprint
        │
        ▼
Ordered profile
        │
        ▼
Deterministic resolver
        │  ├── package/backend checks
        │  ├── region and installation binding
        │  ├── dependency/incompatibility checks
        │  ├── metadata provenance checks
        │  └── winning target map and conflicts
        ▼
Public deployment boundary (deployment.py)
        │  ├── every resolver blocker enforced
        │  └── process inspection fails closed
        ▼
Transactional apply core (engine.py)
        │  ├── target identity verification
        │  ├── previous deployment verification
        │  ├── one-time vanilla baseline
        │  ├── durable journal and snapshots
        │  ├── staging and atomic commit
        │  └── rollback and ownership manifest
        ▼
Game Persistent/dat
```

## Public boundaries and low-level cores

New code must import `ManagerStore` from `umml_manager.library` or the package root, and `ApplyEngine` from `umml_manager.deployment` or the package root.

`store.py` and `engine.py` are the mature low-level implementations. They remain separate so import/storage mechanics and transaction/recovery mechanics can evolve without turning one file into a divine monolith. The public boundary modules add policy that must not be bypassed:

- `library.py` serializes the full identity-selection, copy, and registry transaction;
- `library.py` exposes a typed `UnrecognizedModError` for provider compatibility fallbacks;
- `deployment.py` rejects every blocker produced by the resolver;
- `deployment.py` blocks writes when process inspection fails or the game is running.

Compatibility aliases are installed during package initialization for historical internal imports. Tests assert those aliases resolve to the guarded public classes. This bridge is transitional and must remain reload-safe until raw imports are removed incrementally.

## Library

The library preserves imported source packages under immutable mod ID/version paths. An imported record contains descriptive metadata, provider provenance, source location, preparation state, and a target-file manifest when prepared.

Updating a mod must not replace the bytes representing an already imported version. Older records remain reproducible until the user removes them intentionally.

Identity allocation is part of the import transaction. Threads in one process serialize through a mutex; separate processes serialize through an advisory file lock. This prevents two simultaneous imports from selecting the same record ID and leaving one immutable source orphaned from the registry.

An identical re-import of the same ID/version is idempotent: it returns the existing record instead of replacing preparation paths, target manifests, or metadata provenance with an unprepared record.

## Package recognition

Strict import accepts recognizable UMML or Hachimi roots. Provider-confirmed loose legacy archives may use a compatibility normalizer, but only after strict import raises the typed `UnrecognizedModError`. Other storage failures, registry failures, and permission errors are not reinterpreted as legacy archive layouts.

Untrusted inputs remain bounded by entry count, expanded size, path length, traversal, link, special-file, and regular-tree checks.

## Preparation

Legacy mods provide named files under `assets/`. The preparation adapter uses the readable metadata database to resolve game hashes and encryption keys, producing a hash-addressed prepared tree.

Preparation is cache construction, not installation. It may run while the game is open and must never write to `Persistent/dat`.

Prepared records store the metadata fingerprint used to build them. When current metadata is known, a missing or mismatched preparation fingerprint is a blocker. An old cache without provenance is not treated as probably current.

## Profiles

A profile is an ordered list of stable mod IDs. Profiles do not contain imperative install/uninstall instructions.

```json
{
  "name": "Dark UI",
  "enabled": [
    "creator.interface-base",
    "creator.dark-mode",
    "creator.icon-override"
  ],
  "region": "global",
  "installation_key": "steam-global"
}
```

Later entries have higher priority for overlapping target paths. A bound profile cannot deploy when the target installation identity is missing or different.

Ordinary membership and load-order edits preserve the binding already stored on the profile. Rebinding is a separate user action and requires a verified current installation, so browsing another target cannot silently retarget a profile.

## Resolver

The resolver is a pure planning stage. Given the same profile, target identity, metadata fingerprint, and library records, it produces the same result regardless of filesystem enumeration order, network availability, locale, or current time.

A resolution records:

- missing and unprepared mods;
- unsupported deployment backends;
- wrong regions and installation identities;
- stale or unverified prepared caches;
- missing dependencies and declared incompatibilities;
- invalid paths and hashes;
- one winner for each target path;
- every overridden provider for conflicted paths.

The resolver does not touch the game directory. Every item in `Resolution.blocking_issues` must also be enforced by the public deployment boundary.

## Deployment

The public deployment engine receives a complete resolution and refuses it when any blocker category is non-empty. This check is repeated at the backend boundary even when the GUI already disabled Apply.

Before writing, deployment verifies:

- process inspection succeeded and the game is closed before any interrupted recovery;
- process state is checked again immediately before a recovery rollback;
- prepared sources still match their recorded hashes;
- target paths are safe and relative;
- the target installation matches active state and baselines;
- active managed files still match the previous deployment manifest;
- the vanilla baseline needed for restoration is available.

It then captures recovery snapshots, checks process state again, compares active ownership with the snapshots, and confirms the live targets still match those snapshots. Only then does mutation begin. Replacements commit atomically, installed hashes and target ownership are recorded, and a failed transaction rolls back to the verified snapshots.

## Vanilla baseline

The first untouched game file observed for a managed target becomes its vanilla baseline. Manager owns that target-bound baseline independently from legacy UMML's shared `dat.backup` directory.

When taking over files previously managed by legacy UMML, deployment first compares every unowned target with the corresponding sibling `dat.backup` entry. A complete, explicitly approved migration copies the originals into Manager's baseline, records their hashes and legacy provenance, and leaves `dat.backup` untouched. The complete required set is preflighted before any copy, so a missing or unsafe original cannot produce a partial logical migration.

For a target that did not exist in vanilla, restoration means deleting the manager-created target after verifying it still matches the active deployment.

The manager must never refresh vanilla from a modded file merely because a game update or another tool changed the target.

Likewise, a pre-existing target that already has the requested mod hash is not adopted as manager-owned unless a valid baseline for that path already exists. Matching mod bytes are not evidence of known vanilla bytes.

## External-change protection

The active deployment manifest records the hash and owning mod for each managed target. If the target later differs, UMML Manager assumes another tool, game update, or manual operation changed it.

Normal apply stops instead of overwriting that file. Recovery may explicitly force a desired state, but the UI and CLI must make that decision visible. Force can override a mismatch that existed before snapshot capture; it cannot override another change detected after the snapshots were taken.

## Providers

Providers fetch metadata and archives, then hand them to the public library boundary. They do not prepare assets, resolve profiles, or deploy files.

The GameBanana provider records submission and selected-file identity so update checks compare remote files with the installed source record rather than guessing from filenames. Region inference is centralized so the original Japanese listing and the explicitly named Global listing are not confused.

## Frontends

The Tk GUI and CLI share the same public library, resolver, and deployment boundaries. Frontends may format plans or ask for confirmation, but they must not implement separate load order, conflict, target-identity, process, or backup behavior.

The GUI adds contextual controls and verified diagnostics. These improve explanation but are not the security boundary. Direct method calls and CLI calls still reach the same backend guards.

The frozen package uses `umml_manager_packaged.py` as a small dispatcher:

```text
umml-manager-bin gui
umml-manager-bin cli <arguments>
umml-manager-bin --legacy-host
```

The source installer carries the same Python application boundary, including the legacy Studio entry point, auto-detection package, platform helpers, and `UMML_data`. Tk and Pillow are required for the graphical manager; missing preparation/Studio dependencies are reported rather than hidden behind a nominally successful install.

## Legacy Studio

Every Studio card launches the same compatibility host, which exposes mutating actions. The whole host therefore requires the game closed. Individual legacy callbacks retain their own guards, and the host watches the game for its entire lifetime.

## Runtime boundary

The manager does not accept native or executable runtime plugins. Optional in-game integration is a separate protocol and adapter.

The desktop manager retains ownership of downloads, library records, profiles, planning, baselines, deployment, updates, and rollback. An in-game adapter may request status or queue a profile for restart only through an exact-build, separately disableable boundary. Unknown builds fail closed.

## Operational rule

The manager can download, import, prepare, and plan while the game runs. Applying, restoring, or opening the legacy Studio is blocked until the game closes. If the manager cannot determine process state, writes remain blocked. This boundary is intentionally boring, which is an excellent property for software holding the only clean copy of someone's game files.

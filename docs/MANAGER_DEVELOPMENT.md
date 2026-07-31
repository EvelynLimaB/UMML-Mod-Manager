# Uma Mod Manager development guide

This guide describes how to change Uma Mod Manager without weakening its import, deployment, recovery, privacy, compatibility, or release guarantees. Read [MANAGER_ARCHITECTURE.md](MANAGER_ARCHITECTURE.md) first.

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt -r requirements-build.txt
python -m pip check
```

The GUI requires Python with Tk support. Debian and Ubuntu developers may need `python3-tk`. Linux package work additionally needs `dpkg-deb`, AppStream/desktop validators, Xvfb, and the normal compiler/runtime libraries used by PyInstaller.

Run from source:

```bash
python -m umml_manager.gui
python -m umml_manager --root /tmp/uma-mod-manager-dev list
```

Always use a temporary `--root` for experiments unless the task explicitly needs a disposable copy of an existing test library. Automated tests must never discover and mutate a real game installation.

## Package map

```text
umml_manager/
├── cli.py                     command-line interface
├── deployment.py             transactional deployment and recovery
├── engine.py                 guarded public deployment boundary
├── gui.py                    Tk application shell and shared state
├── store.py                  immutable library, profiles and critical state
├── resolver.py               deterministic profile/conflict planning
├── library.py                import and preparation orchestration
├── manifest.py               package metadata and validation
├── options.py                profile-scoped package choices
├── mod_inspection.py         source-bundle and target analysis
├── package_builder.py        creator workspaces
├── installations.py          installation discovery and identity
├── process.py                game-running detection
├── validation.py             read-only diagnostics
├── support_bundle.py         bounded privacy-scrubbed tester reports
├── veterans.py               read-only external roster snapshots
├── ui_*.py                   focused pages, dialogs and action mixins
└── providers/
    └── gamebanana.py          remote metadata, downloads and provenance
```

`umml_manager_packaged.py` is the frozen GUI/CLI dispatcher. Keep product logic inside the package rather than hiding behavior in launchers or packaging scripts.

The preserved `UMML.py`, `UMML_core.py`, `umml_platform.py`, and `umml_autodetect/` paths are compatibility code. New product behavior belongs in native Manager modules unless there is a documented shared-service reason.

## Core invariants

Changes to the store, resolver, preparation, UI, or deployment engine must preserve:

1. **Imported sources are immutable.** Edits create a workspace and a new version.
2. **Preparation is automatic and separate from deployment.** It never writes game files.
3. **One authored source may own multiple final targets.** Source-bound options remain isolated.
4. **Profiles are ordered and deterministic.** Later enabled claims win ordinary conflicts.
5. **Resolution completes before writes.** Every blocker and winner is known first.
6. **Vanilla is captured only from verified originals.** Modded bytes never refresh a baseline.
7. **External changes are protected.** Unknown live state is not overwritten silently.
8. **Apply is transactional.** Failure restores or preserves deterministic recovery evidence.
9. **The game must be closed for writes.** Unknown process state blocks mutation.
10. **Providers do not deploy.** They return metadata and archives to the store.
11. **Runtime code is outside ordinary packages.** Injection and native hooks require separate adapters and gates.
12. **Critical corruption fails closed.** Preferences may be quarantined; deployment evidence may not be discarded.
13. **Public rebranding does not split user state.** Stable technical identifiers remain stable until an explicit migration passes.
14. **Tester evidence is bounded and scrubbed.** Support reports do not become a new data-exfiltration format.

A patch that makes the happy path shorter by violating one of these is not an optimization. It is a delayed support ticket wearing running shoes.

## Model and state changes

Serialized records need explicit versioning or backward-compatible defaults. When adding a field:

- choose a safe default for old records;
- keep unknown provider metadata intact where practical;
- reject malformed target paths;
- never silently reinterpret an existing field;
- add round-trip, migration, corruption, and concurrent-update tests as applicable;
- document whether the field is portable package metadata or machine-local state.

Do not store machine-specific absolute paths inside portable manifests.

## Import and preparation safety

Archive and folder imports must reject before immutable copying:

- `..` traversal;
- absolute and Windows drive paths;
- symbolic and hard links;
- devices, FIFOs, sockets, and special entries;
- duplicate normalized outputs;
- excessive member names, counts, or expanded size;
- encrypted entries that cannot be inspected;
- output escaping the staging directory.

New archive formats need equivalent pre-extraction metadata and bounds. Do not support executable installers by launching them.

Preparation changes must test:

- automatic queueing after import;
- migration from older preparation formats;
- one source mapping to many targets;
- profile options selecting isolated source roots;
- failure preserving source and prior verified cache;
- queue continuation after one package fails;
- metadata-change invalidation;
- imported-source byte immutability.

There is no supported user workflow where someone repeatedly presses Prepare until the machine becomes emotionally convinced.

## Resolver changes

The resolver must remain deterministic for the same library, installation identity, metadata fingerprint, and profile. Avoid filesystem iteration order, current timestamps, locale-dependent sorting, or network data during resolution.

Every resolution exposes:

- missing or unknown mod IDs;
- unsupported or stale preparation;
- invalid profile options;
- dependencies and incompatibilities;
- region and installation mismatches;
- relative load-order violations;
- exact target winners and shadowed claims;
- enough provenance to explain each decision.

Tests should use tiny synthetic prepared trees and assert exact winners and blockers.

## Deployment and recovery changes

Use a temporary game tree. Test at least:

- vanilla to one mod;
- one winner to another conflicting winner;
- profile to empty profile;
- newly created targets with no vanilla file;
- missing or changed prepared source;
- external target mutation;
- mutation between initial verification and transaction commit;
- interrupted recovery while the game runs or process inspection fails;
- already matching mod bytes with no trusted baseline;
- complete and incomplete legacy-backup migration;
- staging failure;
- commit failure and rollback;
- repeated unchanged application;
- game/Manager installation identity mismatch;
- recovery evidence preservation after every failure.

`force=True` is an explicit recovery override. It must not become the default or an internal method for making tests stop complaining.

## Provider and external-tool changes

Preserve when available:

- provider/project name;
- submission and selected file IDs;
- original filename, author, source URL, version and update time;
- downloaded SHA-256 and size;
- license and attribution information.

Provider tests should use fixtures or a local fake server. Live smoke tests remain optional and separately reported because remote APIs are allowed to have bad days.

External tools:

- launch without `shell=True`;
- run in isolated workspaces where possible;
- never inherit deployment/baseline/recovery privileges;
- never elevate the Manager GUI;
- keep exact upstream credits, links, versions and license status;
- import bounded output through a versioned adapter.

## GUI changes

The GUI fronts the same store, resolver, safety checks, and engine used by the CLI. Do not reimplement profile semantics in Tk callbacks.

Manually and synthetically verify:

1. profiles, selection, options, load order and saved state remain aligned;
2. import and preparation failures preserve source and UI usability;
3. conflict preview matches CLI planning;
4. Apply and write-capable Studio actions block while game status is running or unknown;
5. long work disables relevant actions and restores them afterward;
6. every error/dialog is parented, raised, focused and usable at supported sizes;
7. System/Light/Dark changes apply immediately and persist;
8. Windows folder actions and Linux desktop integration work;
9. support-bundle creation runs in background, rejects unsafe destinations and explains privacy review;
10. no visible maintenance action asks users to prepare, repair, or migrate normal imports manually.

## Support-bundle changes

`support_bundle.py` is a strict data minimization boundary.

Permitted output is limited to:

- build/runtime/platform information;
- configuration-presence flags;
- bounded high-level package/profile summaries;
- privacy-scrubbed read-only diagnostics;
- collection warnings and a privacy manifest.

Do not include raw settings, library records, profiles, game paths, source archives, prepared payloads, baselines, active state, journals, roster snapshots, downloaded files, credentials, tokens, cookies, authorization fields, or known viewer/account values.

Tests must cover:

- representative private-key variants;
- Unix and Windows-style paths;
- directory, regular-file and symlink destinations;
- atomic replacement;
- long free-form text bounds;
- collector failure;
- readable ZIP contents;
- documentation telling users to inspect before upload.

## Community Test release changes

Read [RELEASE_PROCESS.md](RELEASE_PROCESS.md) and [TESTING_AND_FEEDBACK.md](TESTING_AND_FEEDBACK.md).

A named testing build updates together:

- `MANAGER_VERSION`;
- portable/AppStream version and Git tag;
- `MANAGER_CHANGELOG.md`;
- README and player-guide examples;
- versioned `docs/releases/` notes;
- AppStream release entry;
- release-workflow default and notes path;
- package payload docs;
- issue forms when evidence needs change;
- tests and `scripts/audit_release.py` expectations.

Run:

```bash
python scripts/audit_release.py --tag v0.2.0-alpha.19
```

Published artifacts are immutable by tag, commit, filename and SHA-256. A changed binary receives a new version. Do not upload a replacement and ask everyone to pretend the old checksum never happened.

## Required checks

```bash
python -m compileall -q \
  umml_manager umml_manager_packaged.py tests \
  scripts/audit_manager.py scripts/audit_branding.py scripts/audit_release.py

python scripts/audit_manager.py
python scripts/audit_branding.py
python scripts/audit_release.py
python -m unittest discover -s tests -p 'test_manager*.py' -v
bash scripts/check_manager.sh
```

Shell changes also require:

```bash
bash -n \
  install-manager.sh uninstall-manager.sh \
  scripts/build_manager_frozen.sh \
  scripts/build_manager_deb.sh \
  scripts/build_manager_appimage.sh \
  scripts/manager_main_gate.sh
```

For packaging changes:

```bash
scripts/build_manager_frozen.sh
scripts/build_manager_deb.sh
scripts/build_manager_appimage.sh

dpkg-deb --info dist/umml-manager_*_amd64.deb
dpkg-deb --contents dist/umml-manager_*_amd64.deb
```

Use the manual testing-release workflow first with publication disabled. Real-machine tests remain required before publication or promotion.

## Test fixtures

Fixtures must be synthetic or redistributable. Do not commit:

- game bundles or extracted assets;
- encrypted or decrypted metadata;
- proprietary mod archives;
- user libraries, profiles, baselines, journals, support reports, or roster data;
- Wine prefixes, Steam credentials, or personal paths;
- generated package artifacts.

A useful deployment fixture contains a few text files named like game hashes and a minimal Manager record. The engine cares about bytes, paths, hashes, ownership and failure boundaries; it does not need copyrighted horse-girl geometry to prove those properties.

## Pull-request scope

A good Manager PR explains:

- affected layer and user workflow;
- before/after state model;
- compatibility and migration behavior;
- safety, privacy, failure and rollback behavior;
- automated checks;
- real-machine, real-mod, provider or recovery checks still missing;
- third-party attribution and license impact.

Keep architecture, deployment, packaging, release, provider, runtime and destructive-recovery work draft until its applicable real-world gates pass. Green CI is evidence, not absolution.

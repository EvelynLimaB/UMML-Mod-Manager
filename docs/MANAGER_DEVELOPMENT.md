# UMML Manager development guide

This guide describes how to change UMML Manager without weakening its deployment
and recovery guarantees. Read `MANAGER_ARCHITECTURE.md` first.

## Development setup

Linux:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt -r requirements-build.txt
```

The GUI requires a Python build with Tk support. Debian and Ubuntu developers may
need `python3-tk`. Building Debian packages additionally requires `dpkg-deb` and
the normal compiler/runtime libraries used by PyInstaller.

Run the manager from source:

```bash
python -m umml_manager.gui
python -m umml_manager --root /tmp/umml-manager-dev list
```

Always use a temporary `--root` for experiments unless the task explicitly needs
an existing test library.

## Package map

```text
umml_manager/
├── cli.py                 command-line interface
├── engine.py              transactional deployment and recovery
├── gui.py                 Tk desktop interface
├── legacy_adapter.py      legacy assets/ metadata preparation
├── models.py              serialized domain records
├── process.py             game-running detection
├── resolver.py            profile and conflict resolution
├── store.py               library, profiles, cache and state
└── providers/
    └── gamebanana.py      remote metadata, downloads and updates
```

`umml_manager_packaged.py` is the frozen GUI/CLI dispatcher. Keep product logic
inside the package rather than putting behavior into launchers or packaging
scripts.

## Core invariants

Changes to the store, resolver, or engine must preserve these rules:

1. **Imported sources are immutable.** Updating a mod creates or selects another
   version; it does not mutate the bytes representing an already imported
   version.
2. **Preparation is separate from deployment.** Named source assets are converted
   into a prepared cache before the game directory is touched.
3. **Profiles are ordered.** Later enabled mods win a target-path conflict.
4. **Resolution is complete before writes.** The engine receives a full desired
   target map, not a stream of imperative install operations.
5. **Vanilla is captured once.** The first untouched game file for a managed path
   is the restoration baseline. Already matching mod bytes must not be adopted
   without a previously verified baseline.
6. **External changes are protected.** If the current target does not match the
   previous deployment manifest or changes after snapshot capture, apply refuses
   to overwrite it.
7. **Apply is transactional.** A failed operation restores the last known valid
   state or leaves enough transaction information for deterministic recovery.
8. **The game must be closed for writes.** Importing, downloading, preparing, and
   planning are allowed while it runs; apply and recovery restore are not.
   Process-inspection failure is a write blocker.
9. **Providers do not deploy.** GameBanana and future providers return metadata and
   archives to the store. They never write game files.
10. **Runtime code is outside the manager.** Native plugins, injection, and Unity
    hooks belong to optional adapters with separate compatibility gates.

A patch that makes a happy-path operation shorter by violating one of these rules
is not an optimization. It is a delayed support ticket.

## Model and state changes

Serialized records need explicit versioning or backward-compatible defaults.
When adding a field:

- choose a safe default for old records;
- keep unknown provider metadata intact where practical;
- reject malformed target paths;
- never silently reinterpret an existing field;
- add a round-trip or migration test.

Do not store machine-specific absolute paths inside portable mod metadata unless
the field is explicitly local state.

## Import safety

Archive imports must reject:

- `..` traversal;
- absolute paths;
- Windows drive paths;
- symbolic and hard links;
- device entries;
- extraction outside the staging directory.

New archive formats need the same validation before extraction. Do not trust a
tool merely because it successfully lists an archive.

Imported executable or native libraries are not accepted as manager mods. If a
future format needs scripts, it requires a separate security and permission
model rather than silently executing files from an archive.

## Resolver changes

The resolver should remain deterministic for the same library and profile.
Avoid filesystem iteration order, current timestamps, locale-dependent sorting,
or network data during resolution.

Every resolution should expose:

- missing mod IDs;
- missing prepared files;
- target winners;
- overridden providers;
- enough provenance to explain why a winner was selected.

Tests should use tiny synthetic prepared trees and assert exact winners.

## Apply-engine changes

Use a temporary game tree in tests. Never run engine tests against a detected
real installation.

Test at least:

- vanilla to one mod;
- one mod to another conflicting mod;
- enabled profile to empty profile;
- newly created targets with no vanilla file;
- missing prepared source;
- external target mutation;
- target mutation between initial verification and transaction commit;
- interrupted recovery while the game is running or process inspection fails;
- an already matching target with no known vanilla baseline;
- migration from legacy `dat.backup` when the installed legacy mod both matches and differs from the requested winner;
- incomplete legacy backup migration with no partial Manager baseline;
- failure during staging;
- failure during commit and rollback;
- repeated application of an unchanged profile.

`force=True` is an explicit recovery override. It must not become the default or
be used internally to make tests pass.

## Provider changes

Provider modules should isolate network-specific response shapes from manager
records. Preserve:

- provider submission ID;
- selected file ID;
- original filename;
- author or submitter metadata;
- source URL;
- remote update timestamp or version when available;
- archive hash after download.

Network tests should use fixtures or a local fake server. Live-provider smoke
tests belong in a separate optional job because remote APIs are allowed to have
a bad day like everyone else.

## GUI changes

The GUI is a frontend to the same store, resolver, and engine used by the CLI.
Do not reimplement profile semantics in Tk callbacks.

Manually verify:

1. profiles can be created and selected;
2. enable/disable state matches the saved profile;
3. move up/down changes deterministic load order;
4. import errors do not corrupt the library;
5. preparation failures leave source records intact;
6. conflict preview matches CLI `plan` output;
7. apply is blocked while the game runs;
8. long work does not permanently freeze controls;
9. every error dialog is parented to the manager window;
10. resizing keeps paths, actions, and the mod list usable.

## Required checks

```bash
python -m py_compile \
  umml_manager/*.py umml_manager/providers/*.py \
  umml_manager_packaged.py tests/test_manager.py
python -m unittest discover -s tests -p 'test_manager.py' -v
bash -n install-manager.sh uninstall-manager.sh \
  scripts/build_manager_frozen.sh scripts/build_manager_deb.sh
```

For packaging changes:

```bash
scripts/build_manager_frozen.sh
scripts/build_manager_deb.sh

dpkg-deb --info dist/umml-manager_*_amd64.deb
dpkg-deb --contents dist/umml-manager_*_amd64.deb
```

Test installation and removal in a disposable Debian/Ubuntu VM or container when
possible.

## Test fixtures

Fixtures must be synthetic or redistributable. Do not commit:

- game bundles or extracted assets;
- encrypted or decrypted game metadata;
- proprietary mod archives;
- user library or state directories;
- account identifiers;
- Wine prefixes or Steam credentials.

A useful fixture contains a few text files named like game hashes and a minimal
manager record describing them. The engine cares about bytes, paths, hashes, and
ownership; it does not need copyrighted game content to prove those properties.

## Pull-request scope

Prefer one architectural concern per PR. A good manager PR explains:

- which invariant or user workflow changes;
- the before and after state model;
- migration or compatibility behavior;
- failure and rollback behavior;
- tests performed;
- real-machine checks still missing.

Do not hide packaging, state migrations, or provider response changes inside a
large GUI redesign.

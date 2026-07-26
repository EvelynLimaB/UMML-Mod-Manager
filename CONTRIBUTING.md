# Contributing to UMML Linux and UMML Manager

This repository contains two independently packaged desktop applications and an experimental runtime protocol. Contributions should preserve the boundary between them instead of quietly turning three codebases into one unusually anxious organism.

## Project map

| Area | Purpose | Main paths |
| --- | --- | --- |
| Legacy UMML | One-folder loading, preview, backup, restore, and platform discovery | `UMML.py`, `UMML_core.py`, `umml_platform.py`, `umml_autodetect/` |
| UMML Manager | Library, profiles, providers, conflicts, editing workspace, and deterministic deployment | `umml_manager/`, `MANAGER_README.md` |
| Runtime bridge | Optional fail-closed protocol for future in-game adapters | `umml_runtime/`, `runtime_bridge/` |
| Packaging | Shared frozen runtimes, Debian packages, AppImages, desktop metadata, checksums | `scripts/`, `packaging/`, `assets/` |
| Documentation | User, architecture, development, release, and safety guidance | `README.md`, `docs/` |

State which area your pull request changes. Large changes spanning layers need a clear reason and should usually be split into stacked draft PRs.

## Before contributing

1. Check the repository and current draft PRs for overlapping work.
2. Reproduce the problem with exact commands and paths, with private information removed.
3. Identify affected products, package formats, platforms, and stored-state formats.
4. Use synthetic or redistributable fixtures.
5. Keep unrelated cleanup out of the patch.
6. Run every check for the layers you touched.
7. Document real-machine or live-service testing that remains undone.

Repository Issues may be disabled. In that case, open a focused draft PR with a complete problem statement rather than a mysterious pile of files and optimism.

## Never commit

Do not commit:

- game executables, bundles, textures, audio, models, or other copyrighted assets;
- encrypted or decrypted game metadata databases;
- `dat`, `dat.backup`, `Persistent`, Wine prefixes, or Steam credentials;
- downloaded mod archives unless their license explicitly permits redistribution;
- virtual environments, Micromamba roots, PyInstaller work directories, AppDirs, downloaded packaging tools, or build outputs;
- manager libraries, profiles, state, vanilla backups, logs, or caches;
- access tokens, cookies, account identifiers, or private crash reports;
- generated DEB/AppImage files in ordinary source commits.

Tests should use tiny generated files that reproduce path, hash, ordering, transaction, archive, provider, or package behavior without including game content.

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Packaging work also needs:

```bash
python -m pip install -r requirements-build.txt
```

On Debian/Ubuntu, development may additionally require:

```bash
sudo apt install \
  appstream-util \
  curl \
  desktop-file-utils \
  dpkg-dev \
  file \
  python3-tk
```

## Coding guidance

- Target Python 3.11 for packaged Linux builds.
- Add type annotations to new manager and runtime code.
- Prefer `pathlib.Path` for new filesystem work.
- Keep GUI, network, filesystem, state, deployment, and packaging responsibilities separate.
- Use explicit exceptions with actionable error messages.
- Keep sorting and serialization deterministic.
- Never pass untrusted provider/archive values to a shell.
- Do not weaken safety checks to support one problematic mod.
- Keep launchers and package scripts thin; product behavior belongs in application code.

`UMML_core.py` is upstream-derived and structurally older than new modules. Avoid format-only rewrites that make upstream comparison and review harder.

## Legacy UMML contributions

### Boundaries

Keep Steam, registry, Wine, Proton, and regional path discovery in `umml_platform.py` and `umml_autodetect/`. Do not spread platform probes through GUI callbacks.

Game-file mutations must remain blocked while the game is running. New mutating operations need the same safety treatment as load, restore, cleanup, and database work on branches where those guards exist.

### Required checks

```bash
python -m py_compile \
  UMML.py UMML_core.py umml_platform.py umml_packaged.py \
  umml_autodetect/*.py
python -m unittest discover -s tests -v
bash -n install.sh uninstall.sh scripts/*.sh
scripts/build_release.sh
```

Branches adding optional legacy extension modules must include those modules in their compile and test commands.

### Manual GUI checks

Verify:

1. startup feedback appears before long path/metadata work;
2. platform selection stays in front of the main window;
3. resizing keeps paths, actions, and progress usable;
4. load and restore create recoverable state;
5. diagnostics report selected paths and readiness evidence;
6. mutating actions are blocked while the game runs;
7. error dialogs are parented to the application window.

## UMML Manager contributions

Read these first:

- `MANAGER_README.md`;
- `docs/MANAGER_ARCHITECTURE.md`;
- `docs/MANAGER_DEVELOPMENT.md`;
- `docs/PACKAGING.md` for package changes;
- `docs/MANAGER_MAIN_PROMOTION.md` for merging the alpha preview into `main`;
- `docs/MANAGER_RELEASE_CHECKLIST.md` for unfinished real-machine gates.

### Manager invariants

The following are review requirements:

1. Imported source versions are immutable.
2. Preparation never writes game files.
3. Profiles are ordered; later entries win conflicts.
4. Resolution completes before deployment begins.
5. Missing or unprepared enabled mods block deployment.
6. Vanilla files are captured once and never refreshed from modded state.
7. Active targets are verified against the previous deployment manifest.
8. Corrupt state fails closed instead of being silently reset.
9. External changes are not overwritten silently.
10. Apply and restore are transactional and blocked while the game runs.
11. Providers download/import but never deploy.
12. Native or injected plugins remain outside both manager package formats.
13. The DEB and AppImage use the same frozen runtime and user data model.

State/model changes need backward-compatible defaults or an explicit migration. Never silently reinterpret an existing field.

### Required checks

```bash
python -m py_compile \
  umml_manager/*.py umml_manager/providers/*.py \
  umml_manager_packaged.py tests/test_manager.py
python -m unittest discover -s tests -p 'test_manager.py' -v
bash -n \
  install-manager.sh \
  uninstall-manager.sh \
  scripts/build_manager_frozen.sh \
  scripts/build_manager_deb.sh \
  scripts/build_manager_appimage.sh
```

### Test expectations

Use a temporary manager root and synthetic game tree. Depending on the change, test:

- deterministic conflict winners;
- empty, missing, and unprepared profiles;
- unsafe archive paths, links, special files, entry counts, and expanded-size limits;
- preparation failures;
- initial and repeated deployment;
- profile switching;
- restoration to vanilla;
- manager-created targets without a vanilla original;
- missing or changed prepared files;
- external target changes;
- corrupt registries and active state;
- staging/commit failure and rollback;
- Windows and Linux process parsing.

Automated tests must never discover and modify a real game installation.

### GUI verification

Confirm profiles, enable/disable, load-order movement, imports, preparation, conflict preview, update checks, path selection, game-running blocks, error handling, and resizing. CLI and GUI must use the same resolver and engine.

## Provider contributions

A provider supplies metadata and original downloaded archives to the store. It must not know the game `dat` path or deploy files.

Preserve where available:

- provider name;
- submission/project ID;
- selected file/release ID;
- author/submitter;
- original filename and source URL;
- remote version/update timestamp;
- downloaded SHA-256;
- third-party license information.

Use response fixtures or a local fake server for deterministic tests. Live API smoke tests should be optional and must not require personal credentials.

## Archive contributions

Every archive format must reject before extraction:

- parent traversal;
- absolute and drive-letter paths;
- symbolic and hard links;
- devices, FIFOs, and special entries;
- encrypted entries that cannot be safely inspected;
- excessive member-name lengths;
- excessive file counts;
- excessive declared expanded size;
- output outside the staging directory.

Do not support executable installers by launching them. Broader formats such as 7z/RAR require equally inspectable metadata and bounded extraction before being advertised.

## Runtime bridge contributions

The runtime bridge is optional and fail-closed:

- loopback communication only;
- authentication on every command;
- protocol and message-size limits;
- exact-build compatibility gates;
- unknown builds expose no hot-reload features;
- profile changes are queued for restart;
- injection and Unity hooks stay in separately disableable adapters;
- no save, account, database, or network modification;
- no arbitrary executable plugin loading.

Runtime checks:

```bash
python -m py_compile umml_runtime/*.py tests/test_runtime.py
python -m unittest discover -s tests -p 'test_runtime.py' -v
cargo test --manifest-path runtime_bridge/Cargo.toml
```

The Rust protocol client currently forbids unsafe code. Native hook code belongs outside that core crate and requires independent review and game-build testing.

## Documentation contributions

Documentation must distinguish:

- legacy UMML from UMML Manager;
- source installers from DEB and AppImage packages;
- package contents from shared user data;
- safe offline work from game-file writes;
- implemented features from proposed runtime work;
- tested platforms from merely architecture-compatible platforms.

Use exact commands and file names. Mark destructive/recovery operations and state what package removal preserves.

Do not place a package's checksum inside documentation embedded in that same package. Generate and publish checksums externally after artifacts are final.

## Packaging contributions

### Product boundaries

```text
umml-linux      /usr/lib/umml          umml, umml-doctor
umml-manager    /usr/lib/umml-manager  umml-manager, umml-manager-cli
manager source  ~/.local/share/umml-manager-app
manager data    ~/.local/share/umml-manager
```

The DEB, AppImage, source install, and legacy loader must not claim each other's application files. Maintain separate versions where appropriate, desktop entries, icons, AppStream metadata, and payload boundaries.

### Shared manager runtime rule

Build once:

```bash
scripts/build_manager_frozen.sh
```

Then package the unchanged bundle twice:

```bash
scripts/build_manager_deb.sh
scripts/build_manager_appimage.sh
```

The AppImage build must extract the result and compare its embedded `umml-manager-bin` against the original frozen bundle. Do not maintain a second PyInstaller spec or package-specific copy of application code.

### Package validation

```bash
dpkg-deb --info dist/umml-manager_*_amd64.deb
dpkg-deb --contents dist/umml-manager_*_amd64.deb

desktop-file-validate \
  packaging/linux/io.github.evelynlimab.ummlmanager.desktop \
  packaging/appimage/io.github.evelynlimab.ummlmanager.desktop
appstream-util validate-relax \
  packaging/linux/io.github.evelynlimab.ummlmanager.metainfo.xml

APPIMAGE_EXTRACT_AND_RUN=1 \
  dist/umml-manager_*_x86_64.AppImage --version
APPIMAGE_EXTRACT_AND_RUN=1 \
  dist/umml-manager_*_x86_64.AppImage --cli --help
```

Generate checksums only after both artifacts are final:

```bash
(
  cd dist
  sha256sum \
    umml-manager_*_amd64.deb \
    umml-manager_*_x86_64.AppImage \
    > SHA256SUMS
  sha256sum -c SHA256SUMS
)
```

When changing a manager release, update together:

- `MANAGER_VERSION`;
- `MANAGER_CHANGELOG.md`;
- README installation examples;
- manager AppStream release metadata;
- version tests;
- CI/release artifact names.

## Pull-request description

Include:

- affected product/layer/package format;
- problem and reproduction;
- design and alternatives;
- state or migration impact;
- safety and rollback behavior;
- automated and manual checks;
- platforms tested;
- live-service or real-game checks still missing;
- third-party tools, sources, hashes, and licenses.

Keep architecture, provider, packaging, and runtime work as draft PRs until the required real-machine checks are complete. Green CI is necessary, not magical.

## Review checklist

- [ ] Scope and affected layer are clear.
- [ ] No game data, user state, secrets, downloaded tools, or generated binaries are committed.
- [ ] Relevant tests were added or updated.
- [ ] Changed-layer checks pass.
- [ ] Failure and recovery behavior is documented.
- [ ] User docs match commands and paths.
- [ ] Both package formats use the same frozen runtime.
- [ ] Packaging metadata matches version/changelog.
- [ ] Third-party licensing and tool hashes are compatible and attributed.
- [ ] Untested platforms and live services are named honestly.

## Security reports

Do not publish credentials, private user data, exploitable archive samples, or account-sensitive behavior in a public PR. Follow [SECURITY.md](SECURITY.md) for private reporting guidance.

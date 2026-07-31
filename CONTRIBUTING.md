# Contributing to UMML-Manager

UMML-Manager is a cross-platform mod manager and mod-development workspace for **Umamusume Pretty Derby**, forked from the original UMML project.

The repository's forward direction is the Manager. Original UMML code remains as a compatibility layer until native replacements reach feature parity and pass safety, deployment, and restoration tests.

Contributions are especially welcome when they make one of these tasks easier:

- discovering and installing a mod;
- understanding what a mod affects;
- configuring characters, dresses, parts, or optional components;
- creating and validating a package;
- testing and updating a mod safely;
- recovering to vanilla;
- integrating a licensed external tool with proper provenance;
- replacing legacy UI with a clearer native workflow.

## Project map

| Area | Purpose | Main paths |
| --- | --- | --- |
| Manager application | Library, profiles, providers, automatic preparation, inspection, conflicts, UI, deployment, and recovery | `umml_manager/`, `umml_manager_packaged.py` |
| Creator tooling | Package workspaces, manifests, source analysis, targeting, options, compatibility, and external-tool adapters | `umml_manager/package_builder.py`, `umml_manager/mod_inspection.py`, `docs/MOD_CREATOR_GUIDE.md` |
| Compatibility Studio | Original UMML loader and editor behavior preserved behind Manager guards | `UMML.py`, `UMML_core.py`, `umml_platform.py`, `umml_autodetect/` |
| Runtime experiment | Optional fail-closed protocol for future in-game adapters | `umml_runtime/`, `runtime_bridge/` |
| Packaging | Windows portable, frozen runtime, Debian package, AppImage, desktop metadata, checksums | `scripts/`, `packaging/`, `assets/` |
| Documentation | User, creator, architecture, development, release, safety, and attribution guidance | `README.md`, `MANAGER_README.md`, `docs/` |

State which area your change affects. Large architecture, provider, deployment, or runtime work should normally begin as a draft pull request.

## Before contributing

1. Read [docs/PROJECT_VISION.md](docs/PROJECT_VISION.md).
2. Check open pull requests for overlapping work.
3. Reproduce the problem with exact steps and private information removed.
4. Identify affected platforms, package formats, installations, providers, and stored-state versions.
5. Use synthetic or redistributable fixtures.
6. Keep unrelated formatting or cleanup out of functional patches.
7. Run every check for the layers you changed.
8. State real-game, real-machine, network, or destructive-recovery testing that remains undone.

## Never commit

Do not commit:

- game executables, bundles, textures, audio, models, animations, or other copyrighted assets;
- encrypted or decrypted game metadata databases;
- real `Persistent/dat`, `dat.backup`, Wine prefixes, or Steam credentials;
- real Manager libraries, profiles, baselines, active state, journals, snapshots, logs, or caches;
- real veteran-roster or account data;
- downloaded mod archives without redistribution permission;
- external tools without a compatible license or explicit permission;
- access tokens, cookies, account identifiers, private crash reports, or personal paths;
- virtual environments, Micromamba roots, PyInstaller work directories, AppDirs, downloaded packaging tools, DEBs, AppImages, portable ZIPs, or other generated outputs.

Tests should generate tiny fixtures that reproduce path, hash, archive, option, conflict, state, transaction, provider, platform, or package behavior without game content.

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

Windows contributors may use PowerShell and the equivalent `.venv\Scripts\Activate.ps1` environment.

## Coding guidance

- Target the Python version declared by the package workflows.
- Add type annotations to new Manager and runtime code.
- Prefer `pathlib.Path` for new filesystem behavior.
- Keep GUI, network, provider, state, filesystem, preparation, planning, deployment, and packaging responsibilities separate.
- Use explicit exceptions with actionable messages.
- Keep serialization and conflict ordering deterministic.
- Never pass provider, archive, manifest, or external-tool input to a shell.
- Never weaken a safety invariant merely to accept one malformed package.
- Keep launchers and package scripts thin; product behavior belongs in application code.
- Do not claim detected character, dress, part, or content metadata without evidence.
- Ordinary creator flows should not require JSON editing.
- Internal preparation and migration should be automatic, not user-operated maintenance.

`UMML_core.py` is upstream-derived and structurally older than new modules. Avoid format-only rewrites that make upstream comparison harder. New work should extract reusable services instead of enlarging the compatibility monolith.

## Manager invariants

These are review requirements:

1. Imported source versions are immutable.
2. Preparation and source analysis never write game files.
3. Automatic maintenance remains automatic; Apply remains explicit.
4. Profiles are ordered and deterministic.
5. Resolution completes before deployment begins.
6. Missing, unsupported, stale, or invalid enabled packages block deployment.
7. Vanilla files are captured only from verified originals and are never refreshed from modded state.
8. Active targets are verified against the previous deployment manifest.
9. Corrupt critical state fails closed rather than being silently reset.
10. External changes are not overwritten silently.
11. Apply and restore are transactional and blocked while the game is running.
12. Providers download and import but never deploy.
13. Native or injected tools remain outside ordinary mod packages.
14. Windows, Debian, and AppImage builds use the same state and safety model.
15. Manager-owned windows are parented, focused, and usable at supported sizes.
16. Editing an imported package creates a new workspace and version rather than mutating the source record.

Stored-state changes require backward-compatible defaults or an explicit migration. Never silently reinterpret an existing field.

## Required Manager checks

```bash
python -m py_compile \
  umml_manager/*.py \
  umml_manager/providers/*.py \
  umml_manager_packaged.py

python -m unittest discover -s tests -p 'test_manager*.py' -v
python scripts/audit_manager.py
bash scripts/check_manager.sh
```

Shell changes also require:

```bash
bash -n \
  install-manager.sh \
  uninstall-manager.sh \
  scripts/build_manager_frozen.sh \
  scripts/build_manager_deb.sh \
  scripts/build_manager_appimage.sh
```

Depending on the change, test:

- deterministic conflict winners;
- empty, missing, stale, unsupported, and invalid profiles;
- profile-scoped option defaults and switching;
- one source bundle owning multiple targets;
- overlapping character/component variants;
- unsafe archive paths, links, special entries, counts, sizes, and duplicate names;
- immutable import behavior;
- preparation failure and queue continuation;
- initial and repeated deployment;
- profile switching and vanilla restoration;
- Manager-created targets without vanilla originals;
- missing or changed prepared payloads;
- external target changes;
- corrupt registries, profiles, active state, baselines, and journals;
- interrupted staging, commit failure, rollback, and recovery;
- Windows and Linux process parsing;
- dialog focus, resizing, themes, and button states.

Automated tests must never discover and modify a real game installation.

## Creator-tool contributions

Read:

- [docs/MOD_CREATOR_GUIDE.md](docs/MOD_CREATOR_GUIDE.md);
- [docs/MANAGER_MOD_MANIFEST.md](docs/MANAGER_MOD_MANIFEST.md);
- [docs/MANAGER_ARCHITECTURE.md](docs/MANAGER_ARCHITECTURE.md).

Creator tools should:

- produce or edit normal Manager packages and workspaces;
- preserve source provenance;
- distinguish detected facts from suggestions;
- validate before immutable import;
- create new versions for edits and updates;
- expose compatibility and option metadata through guided controls;
- use external processes for large or separately licensed tools;
- keep game writes behind the normal resolver and deployment engine.

A creator feature is incomplete when the only usable path is “open this JSON and know what to type.” Advanced text editing may remain available, but it is not the primary UX.

## Provider contributions

A provider supplies metadata and original downloaded archives to the store. It must not know the game `dat` path or deploy files.

Preserve when available:

- provider name;
- submission or project ID;
- selected file or release ID;
- author or submitter;
- original filename and source URL;
- remote version and update timestamp;
- downloaded SHA-256 and size;
- third-party license information.

Use fixtures or a local fake server for deterministic tests. Live API smoke tests should be optional and require no personal credentials.

## External-tool adapters

Adapters must record and display:

- original project;
- original authors and contributors;
- source and release links;
- selected local path;
- version when detectable;
- supported platforms;
- output format;
- license status;
- whether code or binaries are bundled.

Do not copy, modify, bundle, or redistribute an external project without a compatible license or explicit permission. Attribution is mandatory but does not create permission.

Launch external tools without `shell=True`, use isolated workspaces where possible, bound imported outputs, and keep process-memory tools outside deployment privileges.

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
- duplicate output paths;
- output outside the staging directory.

Do not support executable installers by launching them. Broader formats such as 7z or RAR require equally inspectable metadata and bounded extraction before being advertised.

## Compatibility Studio contributions

Existing UMML behavior remains guarded for feature parity, but new functionality should not be added there by default.

When touching compatibility code:

- keep platform discovery in `umml_platform.py` and `umml_autodetect/`;
- keep game mutations blocked while the game runs;
- parent and focus dialogs;
- preserve upstream comparison where practical;
- add tests around extracted services;
- document the native replacement path.

Legacy checks include:

```bash
bash scripts/check_legacy.sh
python -m py_compile UMML.py UMML_core.py umml_platform.py umml_packaged.py
```

The preserved compatibility release version is `1.5.0-linux.6`.

## Runtime bridge contributions

The runtime bridge is optional and fail closed:

- loopback communication only;
- authentication on every command;
- protocol and message-size limits;
- exact-build compatibility gates;
- unknown builds expose no mutation features;
- profile changes are queued for restart unless explicitly proven hot-reload-safe;
- injection and Unity hooks stay in separately disableable adapters;
- no save, account, database, ranking, currency, or network modification;
- no arbitrary executable plugin loading.

Run:

```bash
python -m py_compile umml_runtime/*.py tests/test_runtime.py
python -m unittest discover -s tests -p 'test_runtime.py' -v
cargo test --manifest-path runtime_bridge/Cargo.toml
```

## Packaging contributions

Product paths remain stable:

```text
package          /usr/lib/umml-manager
commands         umml-manager, umml-manager-cli
source app       ~/.local/share/umml-manager-app
Linux state      ~/.local/share/umml-manager
Windows state    %LOCALAPPDATA%\UMML Manager
```

Build the frozen Linux runtime once:

```bash
scripts/build_manager_frozen.sh
```

Package that unchanged bundle:

```bash
scripts/build_manager_deb.sh
scripts/build_manager_appimage.sh
```

Validate:

```bash
dpkg-deb --info dist/umml-manager_*_amd64.deb
dpkg-deb --contents dist/umml-manager_*_amd64.deb

desktop-file-validate \
  packaging/linux/io.github.evelynlimab.ummlmanager.desktop \
  packaging/appimage/io.github.evelynlimab.ummlmanager.desktop

appstream-util validate-relax \
  packaging/linux/io.github.evelynlimab.ummlmanager.metainfo.xml
```

Generate checksums only after artifacts are final:

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

When changing a Manager release, update together:

- `MANAGER_VERSION`;
- `MANAGER_CHANGELOG.md`;
- README installation examples;
- AppStream release metadata;
- version tests;
- workflow artifact names.

## Pull-request description

Include:

- affected layer and package formats;
- problem and reproduction;
- design and alternatives;
- state or migration impact;
- safety, failure, and rollback behavior;
- automated and manual checks;
- platforms tested;
- live-service or real-game checks still missing;
- third-party projects, versions, hashes, links, and licenses.

Keep architecture, provider, packaging, runtime, and destructive-recovery changes as draft PRs until their real-machine gates are complete. Green CI is evidence, not absolution.

## Review checklist

- [ ] Scope and affected layer are clear.
- [ ] No game data, user state, secrets, downloaded tools, or generated binaries are committed.
- [ ] Relevant synthetic regressions were added or updated.
- [ ] Changed-layer checks pass.
- [ ] Failure and recovery behavior are documented.
- [ ] User and creator docs match the implementation.
- [ ] Automatic preparation remains automatic.
- [ ] Imported source remains immutable.
- [ ] Windows and Linux behavior are considered.
- [ ] Third-party licensing and attribution are explicit.
- [ ] Untested platforms, services, and game builds are named honestly.

## Security reports

Do not publish credentials, personal paths, private roster data, exploitable archives, account-sensitive behavior, or destructive recovery evidence in a public issue or pull request. Follow [SECURITY.md](SECURITY.md).

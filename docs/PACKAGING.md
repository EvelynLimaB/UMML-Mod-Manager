# Packaging original UMML compatibility and Uma Mod Manager

This repository currently produces two related applications. They share source lineage and some build dependencies, but their payloads, versions, launchers, and state boundaries remain intentionally separate.

| Product | Distribution formats | Commands | Version file |
| --- | --- | --- | --- |
| Original UMML compatibility loader | `umml-linux` DEB/AppImage | `umml`, `umml-doctor` | `VERSION` |
| Uma Mod Manager | `umml-manager` DEB/AppImage/Windows portable | `umml-manager`, `umml-manager-cli`, AppImage flags | `MANAGER_VERSION` |

The technical package and command names remain `umml-manager` during the public rebrand so existing installations upgrade in place and continue using the same library, profiles, baselines, journals, and workspaces. See [BRANDING_AND_COMPATIBILITY.md](BRANDING_AND_COMPATIBILITY.md).

The Manager DEB, AppImage, Windows portable, source installation, and original compatibility loader must not merge application payload directories, desktop IDs, state paths, or version numbers. All Manager formats intentionally share the same external user state for their platform.

## Build environment

Frozen Linux releases target x86_64 and should be built on the oldest supported Ubuntu environment to preserve a reasonable glibc baseline. Current practice uses Ubuntu 22.04 / Linux Mint 21 compatibility.

Install build tools:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt -r requirements-build.txt
sudo apt install \
  appstream-util \
  curl \
  desktop-file-utils \
  dpkg-dev \
  file \
  python3-tk
```

Tkinter and the shared X11/font libraries used by the PyInstaller runtime must be available in the build image.

## Community Test release contract

The current prepared testing release is:

```text
Debian / MANAGER_VERSION: 0.2.0~alpha19
Portable / AppStream:     0.2.0-alpha.19
Git tag:                  v0.2.0-alpha.19
```

Run the exact metadata audit before packaging:

```bash
python scripts/audit_release.py --tag v0.2.0-alpha.19
```

The audit requires the version, README, player guide, changelog, AppStream entry, release notes, tester guide, release process, issue form, workflows, package scripts, frozen-runtime data, and support-bundle tests to agree. The dedicated manual workflow is `.github/workflows/manager-testing-release.yml`.

See [RELEASE_PROCESS.md](RELEASE_PROCESS.md) and [TESTING_AND_FEEDBACK.md](TESTING_AND_FEEDBACK.md).

## Shared frozen runtime

Both Linux package formats begin with exactly one build:

```bash
scripts/build_manager_frozen.sh
```

The dispatcher supports GUI, CLI, compatibility Studio host, and version modes. The DEB and AppImage copy the same bundle unchanged. Package-specific logic belongs only in thin launchers and metadata.

The frozen runtime must include `certifi/cacert.pem`. Network code first resolves a valid target-system trust store and uses certifi only as a portable fallback. Do not set insecure SSL contexts or disable verification to make a package test pass.

The runtime also includes:

- player and creator documentation;
- `TESTING_AND_FEEDBACK.md`;
- `RELEASE_PROCESS.md`;
- versioned Community Test release notes;
- license, notice, citation, branding, architecture, and packaging references;
- the privacy-scrubbed support-bundle implementation and UI.

## Debian package

```bash
scripts/build_manager_deb.sh
```

Expected output:

```text
dist/umml-manager_<MANAGER_VERSION>_amd64.deb
```

For alpha19:

```text
dist/umml-manager_0.2.0~alpha19_amd64.deb
```

The payload lives under `/usr/lib/umml-manager`. Its desktop entry uses `/usr/bin/umml-manager` so a stale user PATH entry cannot shadow the package.

The package metadata displays **Uma Mod Manager** while retaining the technical package name `umml-manager`. Documentation under `/usr/share/doc/umml-manager` includes the tester guide, release process, and exact release notes.

## AppImage

```bash
scripts/build_manager_appimage.sh
```

Expected output:

```text
dist/umml-manager_<DISPLAY_VERSION>_x86_64.AppImage
```

Debian versions use `~alphaN`, while portable versions use `-alpha.N`:

```text
0.2.0~alpha19  ->  umml-manager_0.2.0-alpha.19_x86_64.AppImage
```

The AppDir contains `AppRun`, Uma Mod Manager desktop metadata, icon, AppStream metadata, thin GUI/CLI launchers, documentation, and the unchanged frozen runtime under `usr/lib/umml-manager`.

`AppRun` behavior:

```text
no arguments      -> GUI
--version         -> version output
--cli ...         -> CLI
cli ...           -> CLI compatibility
--legacy-host ... -> original UMML Studio compatibility host
```

The build downloads the official `AppImage/appimagetool` asset over HTTPS and verifies it against the reviewed published SHA-256 digest. GitHub Actions uses `APPIMAGE_EXTRACT_AND_RUN=1`, avoiding a build-time FUSE dependency.

## Windows portable

The native Windows workflow packages the frozen runtime as:

```text
umml-manager_<DISPLAY_VERSION>_win64.zip
```

For alpha19:

```text
umml-manager_0.2.0-alpha.19_win64.zip
```

The extracted directory provides:

```text
Uma Mod Manager.cmd
Uma Mod Manager CLI.cmd
UMML Manager.cmd
UMML Manager CLI.cmd
README-WINDOWS.txt
TESTING_AND_FEEDBACK.md
RELEASE_NOTES.md
```

The first two launchers are public names. The old names are temporary compatibility aliases invoking the same binary and state root.

## Tester support bundle boundary

The GUI exposes **Settings → Create support bundle**. This creates an external ZIP for issue reports; it is not part of the installed package state.

The support report may contain:

- Manager/runtime version and platform information;
- configuration-presence flags;
- bounded high-level package/profile summaries;
- privacy-scrubbed read-only diagnostics;
- collection warnings.

It must not contain game assets, downloaded packages, mod payloads, baselines, transaction contents, roster snapshots, raw settings, credentials, tokens, or known viewer/account fields. Tests cover representative path, key, symlink, and text-size boundaries. Testers must still inspect the JSON before upload.

## Source installation boundaries

Source installation is distinguishable from binary formats:

```text
~/.local/share/umml-manager-app/       source application code
~/.local/share/umml-manager/           library, profiles and deployment state
~/.local/bin/umml-manager-source       source GUI
~/.local/bin/umml-manager-source-cli   source CLI
```

Source uninstallers preserve Manager state, source archives, prepared files, baselines, transactions, downloads, and workspaces.

## Versioning

`VERSION` tracks the preserved Linux port of the original compatibility loader. `MANAGER_VERSION` tracks Uma Mod Manager. Update together:

- `MANAGER_VERSION`;
- `MANAGER_CHANGELOG.md`;
- `README.md` and `MANAGER_README.md` examples;
- Manager AppStream release metadata;
- `docs/releases/<portable-version>.md`;
- the testing and release documentation where a named campaign changes;
- tests expecting the Manager version;
- workflow defaults, artifact names, and release notes.

Generate checksums outside the packages after artifacts are final. Never replace a published file under an existing tag or checksum.

## Validation

```bash
python scripts/audit_manager.py
python scripts/audit_branding.py
python scripts/audit_release.py --tag v0.2.0-alpha.19
bash scripts/check_manager.sh
bash scripts/build_manager_frozen.sh
bash scripts/build_manager_deb.sh
bash scripts/build_manager_appimage.sh
```

For an exact AppImage candidate on the real Bazzite desktop, close the game and run:

```bash
scripts/manager_main_gate.sh \
  --appimage dist/umml-manager_<DISPLAY_VERSION>_x86_64.AppImage \
  --checksums dist/SHA256SUMS \
  --profile Default
```

The gate identifies the package, runs its disposable deployment/recovery self-test, inspects the real saved target and Manager state without repairing them, checks current GameBanana metadata and preview decoding, renders every Tk page, and applies/restores the selected real profile only on copied game files. It exits nonzero if any required check is skipped or fails. Its log can contain local paths and must be sanitized before publication.

Package validation must confirm:

- exact expected filenames, package name, version, architecture, and tag conversion;
- version and CLI startup in every format;
- public Uma Mod Manager names and stable technical identifiers;
- desktop and AppStream metadata;
- complete frozen-runtime tree parity among source bundle, DEB, and AppImage;
- bundled `certifi/cacert.pem` and Pillow imaging support;
- notice, branding, tester, release-process, and release-note documents in finished packages;
- privacy support-bundle regressions;
- external checksum generation and verification.

Real-machine validation must additionally cover:

- AppImage GUI startup on Bazzite/KDE and a second supported distribution;
- Windows portable launch without a Python installation;
- GameBanana browse and download with no certificate override;
- diagnostics showing the selected system or bundled CA source;
- support-bundle creation and manual privacy inspection;
- DEB installation/removal and coexistence with the original compatibility loader;
- shared Manager state across package upgrades and rollback;
- Steam/Proton/Windows detection, Studio tools, profile deployment, restoration, and game-running guards.

Green packaging tools prove that files were assembled consistently. They do not prove that a live desktop, network, game update, or third-party API will cooperate. The universe retains veto power over CI.

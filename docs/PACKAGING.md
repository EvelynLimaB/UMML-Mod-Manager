# Packaging UMML and UMML Manager

This repository produces two Linux applications. They share source references and some build dependencies, but they are intentionally separate products.

| Product | Distribution formats | Commands | Version file |
| --- | --- | --- | --- |
| Legacy loader | `umml-linux` DEB/AppImage | `umml`, `umml-doctor` | `VERSION` |
| Full manager | `umml-manager` DEB/AppImage | `umml-manager`, `umml-manager-cli`, AppImage flags | `MANAGER_VERSION` |

The manager DEB, manager AppImage, source installation, and legacy loader must not merge application payload directories, desktop IDs, state paths, or version numbers. All manager formats intentionally share only the user data root, `~/.local/share/umml-manager` by default.

## Build environment

Frozen releases target x86_64 Linux and should be built on the oldest supported Ubuntu environment to preserve a reasonable glibc baseline. Current practice uses Ubuntu 22.04 / Linux Mint 21 compatibility.

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

## Shared manager frozen runtime

Both manager package formats begin with exactly one build:

```bash
scripts/build_manager_frozen.sh
```

The dispatcher supports GUI, CLI, legacy Studio host, and version modes. The DEB and AppImage copy the same bundle unchanged. Package-specific logic belongs only in thin launchers and metadata.

The frozen runtime must include `certifi/cacert.pem`. Network code first resolves a valid target-system trust store and uses certifi only as a portable fallback. Do not set insecure SSL contexts or disable verification to make a package test pass.

## Manager Debian package

```bash
scripts/build_manager_deb.sh
```

Expected output:

```text
dist/umml-manager_<MANAGER_VERSION>_amd64.deb
```

The manager payload lives under `/usr/lib/umml-manager`. Its desktop entry must use `/usr/bin/umml-manager` so a stale user PATH entry cannot shadow the package.

## Manager AppImage

```bash
scripts/build_manager_appimage.sh
```

Expected output:

```text
dist/umml-manager_<DISPLAY_VERSION>_x86_64.AppImage
```

Debian versions use `~`, while the portable filename uses `-`:

```text
0.2.0~alpha5  ->  umml-manager_0.2.0-alpha5_x86_64.AppImage
```

The AppDir contains `AppRun`, desktop metadata, icon, AppStream metadata, thin GUI/CLI launchers, and the unchanged frozen runtime under `usr/lib/umml-manager`.

`AppRun` behavior:

```text
no arguments      -> GUI
--version         -> version output
--cli ...         -> CLI
cli ...           -> CLI compatibility
--legacy-host ... -> Studio compatibility host
```

The build downloads the official `AppImage/appimagetool` asset over HTTPS and verifies it against the reviewed published SHA-256 digest. GitHub Actions uses `APPIMAGE_EXTRACT_AND_RUN=1`, avoiding a build-time FUSE dependency.

## Source installation boundaries

Source installation is distinguishable from both binary formats:

```text
~/.local/share/umml-manager-app/       source application code
~/.local/share/umml-manager/           library, profiles and deployment state
~/.local/bin/umml-manager-source       source GUI
~/.local/bin/umml-manager-source-cli   source CLI
```

Source uninstallers preserve manager state, source archives, prepared files, baselines, transactions, downloads, and workspaces.

## Versioning

`VERSION` tracks the Linux port of the upstream legacy loader. `MANAGER_VERSION` tracks the independently developed manager. Update together:

- `MANAGER_VERSION`;
- `MANAGER_CHANGELOG.md`;
- `README.md` and `MANAGER_README.md` examples;
- manager AppStream release metadata;
- tests expecting the manager version;
- artifact names and release notes.

Generate checksums outside the packages after both artifacts are final.

## Validation

```bash
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

- exact expected filenames, package name, version, and architecture;
- version and CLI startup in both formats;
- desktop and AppStream metadata;
- complete frozen-runtime tree parity among source bundle, DEB, and AppImage;
- bundled `certifi/cacert.pem` in both package formats;
- external `SHA256SUMS` generation and verification.

Real-machine validation must additionally cover:

- AppImage GUI startup on Bazzite/KDE and a second supported distribution;
- GameBanana browse and download with no certificate override;
- diagnostics showing the selected system or bundled CA source;
- DEB installation/removal and coexistence with legacy UMML;
- shared XDG manager state across DEB and AppImage;
- Steam/Proton detection, Studio tools, profile deployment, restoration, and game-running guards.

Green packaging tools prove that files were assembled consistently. They do not prove that a live desktop, network, game update, or third-party API will cooperate.

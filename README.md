# UMML for Linux

[![Latest release](https://img.shields.io/github/v/release/EvelynLimaB/UMML-Linux?display_name=tag&sort=semver)](https://github.com/EvelynLimaB/UMML-Linux/releases/latest)
[![Python checks](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/python-checks.yml/badge.svg)](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/python-checks.yml)
[![Manager checks](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-checks.yml/badge.svg)](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-checks.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-7651a8.svg)](LICENSE)

Linux, Steam Proton, packaging, and mod-management work for **Umamusume Pretty Derby**.

| Application | Purpose | Package | Commands |
| --- | --- | --- | --- |
| **Legacy UMML** | One-folder loader, preview, backup, restore, and direct editors | `umml-linux` | `umml`, `umml-doctor` |
| **UMML Manager** | Mod library, profiles, GameBanana browser, local detection, conflicts, Studio editors, and verified transactional deployment | `umml-manager` DEB or AppImage | `umml-manager`, `umml-manager-cli`, or AppImage flags |

They can coexist and do not own the same application files or backup state.

> Close the game before either application writes, restores, or edits game data. Downloading, scanning, importing, browsing, preparing, configuring profiles, creating package workspaces, and conflict planning may happen while it runs.

## Downloads

### Legacy UMML

Stable Linux release: **`1.5.0-linux.6`**.

```bash
sudo apt install ./umml-linux_1.5.0-linux.6_amd64.deb
umml-doctor
umml
```

Download the DEB or AppImage from [GitHub Releases](https://github.com/EvelynLimaB/UMML-Linux/releases/latest).

### UMML Manager preview

Current manager preview: **`0.2.0~alpha16`**, developed in [PR #2](https://github.com/EvelynLimaB/UMML-Linux/pull/2).

Until it becomes a permanent Release asset, open the [manager branch workflow runs](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-checks.yml?query=branch%3Aagent%2Fumml-manager-foundation) and download:

- `umml-manager-deb`;
- `umml-manager-appimage`;
- `umml-manager-checksums`.

#### Debian package

```bash
sudo apt install ./umml-manager_0.2.0~alpha16_amd64.deb
/usr/bin/umml-manager
```

The absolute command is useful when testing upgrades from early source previews. The desktop launcher also uses `/usr/bin/umml-manager` directly so `~/.local/bin` cannot silently start an older copy.

#### AppImage

```bash
chmod +x ./umml-manager_0.2.0-alpha16_x86_64.AppImage
./umml-manager_0.2.0-alpha16_x86_64.AppImage
```

CLI mode is available from the same file:

```bash
./umml-manager_0.2.0-alpha16_x86_64.AppImage --version
./umml-manager_0.2.0-alpha16_x86_64.AppImage --cli list
```

The DEB and AppImage are built from the same frozen runtime and use the same user data directory, `~/.local/share/umml-manager`. CI extracts both finished packages and compares their complete embedded runtime trees.

The manager resolves HTTPS trust stores across Fedora/Bazzite and Debian-family systems, honors validated OpenSSL certificate environment variables, and bundles a portable `certifi` fallback. Certificate verification remains mandatory.

Verify either download with the external `SHA256SUMS` artifact:

```bash
sha256sum -c SHA256SUMS
```

## Manager highlights

- guided Steam/Proton/DMM installation detection and prepared-metadata fingerprinting;
- immutable installed source versions and editable workspace copies;
- serialized immutable import identity allocation across threads and processes;
- automatic preparation of compatible imports while profile application remains explicit;
- safe normalization of provider-confirmed loose legacy UMML asset archives, including deeply nested layouts;
- context-aware buttons that follow selection, paging, background-task, profile-blocker, metadata-verification, and live game-process state;
- named profiles with explicit load order and preserved installation identity, plus an explicit verified-target rebinding action;
- native profile-scoped single-choice and multi-choice mod options declared in `umml-mod.json`;
- source-to-target option mapping during preparation, so choices never rename or mutate immutable imported files;
- a guided **New package** workspace builder with an optional configurable variant template;
- blockers for missing dependencies, declared incompatibilities, invalid profile options, wrong regions, wrong or unverified installations, unsupported backends, stale or unverified prepared caches, and invalid manifests;
- fail-closed GUI and CLI deployment through one guarded public engine boundary;
- path-contained, hash-verified deployment with target-scoped active state and vanilla baselines;
- explicit first-run migration that copies legacy `dat.backup` originals into protected manager baselines before taking ownership;
- durable transaction journals, recovery snapshots, baseline integrity records, rollback, and external-change protection;
- corrupt critical state fails closed; corrupt preferences are quarantined and reset with their original bytes preserved;
- bounded ZIP/TAR extraction and local-folder validation for traversal, symlinks, special files, duplicate paths, file counts, and expanded size;
- automatic nested mod-folder discovery without treating every archive or settings file as a mod;
- built-in Global/Japan GameBanana browsing, verified downloads, exact archive provenance, search, sorting, file selection, bounded preview images, and a detail-loading fallback when catalogue rows omit files;
- complete legacy editing features through the built-in Studio compatibility host;
- a lifetime game-process watcher around all legacy Studio entry points;
- verified diagnostics for target paths, metadata integrity, HTTPS trust, registries, transactions, and process inspection;
- explicit provider and deployment-backend contracts for future GameBanana alternatives, Hachimi support, staged updates, and native Studio pages;
- a standard-library AST audit, visible-button callback audit, and adversarial regression/failure-injection tests;
- manager tests run against the same pinned runtime dependencies bundled into one matching DEB/AppImage runtime.

Read [MANAGER_README.md](MANAGER_README.md) for the user workflow, [docs/MANAGER_MOD_MANIFEST.md](docs/MANAGER_MOD_MANIFEST.md) for package configuration, [docs/MANAGER_BSTAR_REVIEW.md](docs/MANAGER_BSTAR_REVIEW.md) for the comparative design pass, [docs/MANAGER_AUDIT.md](docs/MANAGER_AUDIT.md) for the code audit, and [docs/MANAGER_FEATURE_ROADMAP.md](docs/MANAGER_FEATURE_ROADMAP.md) for planned work.

## Basic manager workflow

1. Open the manager and let **Settings** detect the installation and prepare metadata.
2. Browse GameBanana or scan Downloads/custom folders in **Discover**.
3. Import a compatible mod; the manager prepares it automatically when metadata is ready. Mod creators can start from **Library → New package**.
4. Enable and order mods in a profile bound to the intended installation. Use **Configure** for package-declared choices and **Settings → Bind profile here** only when intentionally moving a profile to the currently detected target.
5. Inspect **Conflicts** for file winners and every deployment blocker.
6. Close the game and apply the profile.
7. Use **Studio** for the original loader's editing tools.

## Source installation

```bash
# Legacy loader
chmod +x install.sh
./install.sh

# Manager
chmod +x install-manager.sh uninstall-manager.sh
./install-manager.sh
```

The source installer keeps the complete Manager and legacy Studio source runtime in `~/.local/share/umml-manager-app`, manager data in `~/.local/share/umml-manager`, and exposes explicit `umml-manager-source` commands. It requires Tk and Pillow; missing preparation/Studio dependencies are reported explicitly. Generic compatibility commands prefer the Debian package whenever it is installed.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-build.txt
python -m pip check
python scripts/audit_manager.py
bash scripts/check_manager.sh
```

Documentation starts at [docs/README.md](docs/README.md). Contribution rules are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Runtime bridge

The experimental runtime bridge is separate from the desktop manager packages. It is not an injector yet and remains fail-closed for unknown game builds.

## License

MIT. Third-party mods and downloads retain their original licenses.

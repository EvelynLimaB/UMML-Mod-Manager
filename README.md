# UMML-Manager

[![Python checks](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/python-checks.yml/badge.svg)](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/python-checks.yml)
[![Linux Manager checks](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-checks.yml/badge.svg)](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-checks.yml)
[![Windows Manager checks](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-windows-checks.yml/badge.svg)](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-windows-checks.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-7651a8.svg)](LICENSE)

**UMML-Manager** is a cross-platform mod manager and mod-development workspace for **Umamusume Pretty Derby**. It is a fork and continuation of UMML, redesigned around one slightly desperate objective:

> Make installing mods safe and boring, and make creating mods easy enough that more people actually make them.

The project serves two equally important groups:

- **Players** get automatic installation detection, browsing, imports, profiles, conflicts, configuration, verified deployment, restoration, and diagnostics.
- **Mod creators** get source-bundle inspection, character/dress/part targeting, compatibility editing, configurable variants, editable workspaces, package validation, and a growing set of extraction and analysis tools.

No user should need to manually “prepare” or “re-prepare” a mod. That is internal plumbing and belongs inside the application, where plumbing has traditionally been kept for several excellent reasons.

> **Current status:** `0.2.0~alpha18` preview. Windows portable, Debian package, and AppImage builds exist, but real-machine promotion gates still apply. Keep backups and close the game before applying, restoring, or editing live game data.

## Quick links

- [User guide](MANAGER_README.md)
- [Mod creator guide](docs/MOD_CREATOR_GUIDE.md)
- [Package manifest reference](docs/MANAGER_MOD_MANIFEST.md)
- [Architecture and safety boundaries](docs/MANAGER_ARCHITECTURE.md)
- [Feature roadmap](docs/MANAGER_FEATURE_ROADMAP.md)
- [Documentation index](docs/README.md)
- [Contributing](CONTRIBUTING.md)

## What UMML-Manager does

### For normal play

- Detects supported Steam, Proton, Wine, DMM, and regional installations using one scored discovery engine.
- Browses Global and Japan GameBanana catalogues with bounded previews and exact file selection.
- Imports local archives and folders through path, link, type, count, and size validation.
- Keeps imported mod versions immutable.
- Automatically prepares and analyzes compatible mods in the background.
- Supports named profiles, explicit load order, per-profile mod options, and target binding.
- Explains exact file winners, conflicts, dependencies, incompatibilities, region mismatches, and blockers before deployment.
- Applies and restores profiles transactionally with target-bound vanilla baselines, journals, rollback, integrity checks, and external-change protection.
- Blocks game-file mutations while the game is running.
- Provides Light, Dark, and System appearance modes, diagnostics, and persistent settings.

### For mod development

- Creates clean package workspaces instead of asking creators to assemble mystery folders by hand.
- Inspects authored Unity source bundles and maps them to the final game targets they own.
- Supports one source bundle expanding into multiple final targets.
- Detects likely models, textures, audio, effects, UI, body, hair, face, costume, character IDs, and dress IDs when there is actual evidence.
- Lets creators edit package identity, affected characters, dresses, parts, regions, dependencies, incompatibilities, relative load order, tags, and compatibility notes through normal controls.
- Supports profile-scoped single-choice and multi-choice variants such as character, dress, colour, audio, quality, or optional components.
- Imports edited workspaces as new immutable versions instead of rewriting the original package.
- Preserves an advanced manifest editor for cases the guided UI cannot express yet.
- Keeps the original UMML editing tools available through a guarded compatibility Studio while they are replaced by native workflows.

### Read-only Uma data tools

The Veteran Roster workspace imports validated JSON produced by community tools in the `umadump` / `UmaExtractor` family. It stores scrubbed immutable snapshots, searches and inspects records, and exports JSON or CSV.

Supported provider families currently include:

- `rockisch/umadump`, the original classic `data.json` lineage;
- `NECOtype/UmaExtractor` and compatible updated classic-format forks;
- `Werseter/umadump 2.0`, including `trained_chara_data.json`.

UMML-Manager credits and launches user-supplied external tools, but does not bundle projects that lack a compatible declared license. Attribution is necessary; permission is still annoyingly a separate concept.

## Core design rules

1. Imported source versions are immutable.
2. Preparation and analysis never write game files.
3. Automatic maintenance stays automatic; the user chooses only profile configuration and Apply.
4. Resolution finishes before deployment begins.
5. Unknown package types, game builds, schemas, or state fail closed.
6. Vanilla baselines are captured once from verified originals and never refreshed from modded state.
7. Apply and restore are transactional and blocked while the game is running.
8. Providers download and import but never deploy.
9. Detection is evidence-based. The UI must distinguish known facts from guesses.
10. External projects keep their names, authors, links, and licenses.
11. Creator workflows should produce ordinary manageable packages, not one-off scripts or executable installers.
12. Linux and Windows are first-class targets rather than one being an apologetic afterthought.

## Downloads

### Windows portable

Download the latest `umml-manager-windows-portable` artifact from the [Windows Manager workflow](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-windows-checks.yml?query=branch%3Aagent%2Fumml-manager-foundation), extract the inner ZIP, and run:

```text
UMML Manager.cmd
```

No Python installation is required for the portable build.

### Debian package

```bash
sudo apt install ./umml-manager_0.2.0~alpha18_amd64.deb
/usr/bin/umml-manager
```

### AppImage

```bash
chmod +x ./umml-manager_0.2.0-alpha18_x86_64.AppImage
./umml-manager_0.2.0-alpha18_x86_64.AppImage
```

Until alpha builds become permanent Release assets, download `umml-manager-deb`, `umml-manager-appimage`, and `umml-manager-checksums` from the [Linux Manager workflow](https://github.com/EvelynLimaB/UMML-Linux/actions/workflows/manager-checks.yml?query=branch%3Aagent%2Fumml-manager-foundation).

Verify published artifacts with their external `SHA256SUMS` file:

```bash
sha256sum -c SHA256SUMS
```

## Basic player workflow

1. Launch UMML-Manager and let Settings detect the game installation and metadata.
2. Browse GameBanana or scan local folders in Discover.
3. Import a mod. Compatible packages prepare and analyze themselves automatically.
4. Enable mods in a profile, select any package-declared options, and set load order.
5. Review Conflicts. The Manager explains every blocker and final file winner.
6. Close the game and apply the profile.
7. Switch profiles or restore vanilla through the same verified deployment engine.

## Basic creator workflow

1. Select **Library → New package**, or select an imported mod and use **Inspect & edit**.
2. Add or inspect source assets in the editable workspace.
3. Review detected targets, characters, dresses, and parts.
4. Correct or extend identity, compatibility, dependencies, tags, and profile options.
5. Validate and import the workspace as a new immutable version.
6. Test it in a dedicated profile, review conflicts, apply, and restore.
7. Publish the resulting package with its manifest, credits, version, and compatibility notes.

The longer workflow is in [docs/MOD_CREATOR_GUIDE.md](docs/MOD_CREATOR_GUIDE.md).

## Project layout

| Area | Purpose |
| --- | --- |
| `umml_manager/` | Main application, library, providers, inspection, profiles, UI, resolver, and deployment |
| `docs/` | User, creator, architecture, packaging, safety, and roadmap documentation |
| `tests/` | Synthetic regression, failure-injection, GUI, package, and platform tests |
| `scripts/`, `packaging/` | Native Windows, DEB, AppImage, source-install, metadata, and release tooling |
| `UMML.py`, `UMML_core.py`, `umml_autodetect/` | Original UMML compatibility layer and reusable upstream-derived functionality |
| `umml_runtime/`, `runtime_bridge/` | Optional experimental runtime protocol, kept outside ordinary mod deployment |

Legacy UMML `1.5.0-linux.6` remains preserved for compatibility and historical comparison. UMML-Manager is now the primary product and the repository’s forward direction.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt -r requirements-build.txt
python -m pip check
python scripts/audit_manager.py
bash scripts/check_manager.sh
```

Windows contributors can use the equivalent PowerShell virtual-environment activation and run the same Python checks. Native Windows packaging is exercised by its own workflow.

## Contributing

Mod-manager improvements, creator tools, asset-analysis workflows, provider adapters, package manifests, UI/UX work, documentation, and synthetic tests are all welcome.

Please read [CONTRIBUTING.md](CONTRIBUTING.md). Do not commit copyrighted game assets, decrypted metadata, personal roster data, downloaded mods without redistribution permission, access tokens, or generated packages.

The most valuable contributions are often not glamorous:

- document a real package layout;
- provide a redistributable synthetic fixture reproducing a failure;
- improve character/dress/part detection without inventing certainty;
- make a creator task require fewer unexplained steps;
- replace a legacy editor with a tested native workflow;
- add compatibility metadata to a mod;
- improve a provider adapter while preserving provenance and licensing.

## Lineage, credits, and legal status

UMML-Manager is forked from and preserves the work of the original **UMML** project and its contributors. Third-party mods, extractors, viewers, libraries, and community tools retain their original authorship and licenses.

This project is not affiliated with Cygames. Do not distribute copyrighted game assets or decrypted game databases through this repository.

UMML-Manager is released under the [MIT License](LICENSE). External projects are not relicensed merely because the Manager can launch or consume their output.

# Uma Mod Manager

[![Legacy compatibility checks](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/python-checks.yml/badge.svg)](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/python-checks.yml)
[![Linux Manager checks](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/manager-checks.yml/badge.svg)](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/manager-checks.yml)
[![Windows Manager checks](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/manager-windows-checks.yml/badge.svg)](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/manager-windows-checks.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-7651a8.svg)](LICENSE)

**Uma Mod Manager** is a cross-platform mod manager and mod-development workspace for **Umamusume Pretty Derby**. It is a fork and continuation of [UMML / UmaMusume Mod Loader](https://github.com/tumugu/UmaMusume_Mod_Loader), rebuilt around one practical objective:

> Make installing mods safe and boring, and make creating mods easy enough that more people actually make them.

The application serves two equally important groups:

- **Players** get installation detection, discovery, validated imports, profiles, options, conflict explanations, verified deployment, restoration, and diagnostics.
- **Mod creators** get package workspaces, source-bundle inspection, character/dress/part targeting, compatibility editing, configurable variants, validation, testing, and growing asset/data tools.

No user should need to manually prepare or re-prepare a mod. That is internal plumbing, and plumbing belongs inside the wall rather than beside the Apply button.

> **Current status:** `0.2.0~alpha18` preview. Windows portable, Debian, and AppImage builds are produced by CI. Keep backups, close the game before any write operation, and treat alpha packages as test builds.

## Start here

- [Player guide](MANAGER_README.md)
- [Mod creator guide](docs/MOD_CREATOR_GUIDE.md)
- [Package manifest reference](docs/MANAGER_MOD_MANIFEST.md)
- [Project vision](docs/PROJECT_VISION.md)
- [Architecture and safety boundaries](docs/MANAGER_ARCHITECTURE.md)
- [Branding and compatibility identifiers](docs/BRANDING_AND_COMPATIBILITY.md)
- [Third-party notices and lineage](NOTICE.md)
- [Documentation index](docs/README.md)
- [Contributing](CONTRIBUTING.md)

## Player features

- Detect supported Windows, Steam, Proton, Wine, DMM, and regional installations.
- Browse Global and Japan GameBanana catalogues with exact file selection and bounded previews.
- Import local archives and folders through path, link, type, count, and size validation.
- Keep every imported version immutable.
- Prepare and analyze compatible packages automatically in the background.
- Build named profiles with explicit load order and per-profile package choices.
- Explain exact file winners, dependencies, incompatibilities, region mismatches, stale preparation, and deployment blockers.
- Apply and restore profiles transactionally with target-bound vanilla baselines, journals, rollback, integrity checks, and external-change protection.
- Block game-file mutation while the game is running.
- Preserve settings, profiles, libraries, baselines, and recovery evidence across package upgrades.

## Creator features

- Create clean package workspaces instead of mystery folders and manual hash surgery.
- Inspect authored Unity source bundles and map them to the final game targets they own.
- Support one source bundle expanding into several final targets.
- Suggest likely models, textures, audio, effects, UI, body, hair, face, costume, character IDs, and dress IDs when there is evidence.
- Edit package identity, affected characters, dresses, parts, regions, dependencies, incompatibilities, relative load order, tags, and compatibility notes through normal controls.
- Define profile-scoped single-choice and multi-choice variants for character, dress, colour, audio, quality, or optional components.
- Import edits as new immutable versions instead of rewriting the original package.
- Preserve an advanced manifest editor for cases the guided UI cannot express yet.
- Keep original UMML tools available through a guarded compatibility Studio while native workflows replace them.

## Read-only Uma data tools

The Veteran Roster workspace imports validated JSON produced by community tools in the `umadump` / `UmaExtractor` family. It stores scrubbed immutable snapshots, rejects unrelated output classes, searches and inspects records, and exports JSON or CSV.

Supported provider families include:

- `rockisch/umadump`, the original classic `data.json` lineage;
- `NECOtype/UmaExtractor`, xancia's compatible fork, and related classic-format tools;
- `Werseter/umadump 2.0`, including `trained_chara_data.json`.

Uma Mod Manager credits and launches user-supplied external tools, but does not bundle projects that lack a compatible declared license. Attribution is required; permission remains a separate and inconveniently real concept.

## Core rules

1. Imported source versions are immutable.
2. Preparation and analysis never write game files.
3. Internal maintenance stays automatic; users choose profile configuration and Apply.
4. Resolution finishes before deployment begins.
5. Unknown package types, game builds, schemas, or critical state fail closed.
6. Vanilla baselines are captured from verified originals and never refreshed from modded state.
7. Apply and restore are transactional and blocked while the game is running.
8. Providers download and import but never deploy.
9. Detection is evidence, not certainty or permission.
10. External projects retain their names, authors, links, and licenses.
11. Ordinary creator workflows should not require JSON editing.
12. Windows and Linux are independently validated first-class targets.

## Downloads

Until alpha builds are published as permanent GitHub Releases, use the latest successful workflow artifacts from `main`:

- [Windows portable workflow](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/manager-windows-checks.yml?query=branch%3Amain)
- [Debian and AppImage workflow](https://github.com/EvelynLimaB/Uma-Mod-Manager/actions/workflows/manager-checks.yml?query=branch%3Amain)

Technical package and command identifiers remain `umml-manager` for upgrade compatibility during the rebrand. See [docs/BRANDING_AND_COMPATIBILITY.md](docs/BRANDING_AND_COMPATIBILITY.md).

### Windows portable

Extract the portable archive and run:

```text
Uma Mod Manager.cmd
```

A compatibility launcher named `UMML Manager.cmd` may remain during the migration window.

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

Verify published artifacts using the accompanying checksum file:

```bash
sha256sum -c SHA256SUMS
```

## Player workflow

1. Launch Uma Mod Manager and confirm the detected installation in Settings.
2. Browse GameBanana or scan local folders in Discover.
3. Import a mod and let preparation and analysis complete automatically.
4. Enable packages in a profile, choose package options, and set load order.
5. Review Conflicts until the plan has no blockers.
6. Close the game and apply the profile.
7. Switch profiles or restore vanilla through the same verified deployment engine.

## Creator workflow

1. Select **Library → New package**, or select an imported mod and use **Inspect & edit**.
2. Add or inspect source assets in the editable workspace.
3. Review detected targets, characters, dresses, parts, and content types.
4. Correct or extend identity, compatibility, dependencies, tags, and profile options.
5. Validate and import the workspace as a new immutable version.
6. Test it in a dedicated profile, review conflicts, apply, switch, and restore.
7. Publish the package with its manifest, credits, version, and compatibility notes.

The detailed workflow is in [docs/MOD_CREATOR_GUIDE.md](docs/MOD_CREATOR_GUIDE.md).

## Repository layout

| Area | Purpose |
| --- | --- |
| `umml_manager/` | Main application, library, providers, inspection, profiles, UI, resolver, and deployment |
| `docs/` | Player, creator, architecture, packaging, safety, and roadmap documentation |
| `tests/` | Synthetic regression, failure-injection, GUI, package, and platform tests |
| `scripts/`, `packaging/` | Windows, Debian, AppImage, source-install, metadata, and release tooling |
| `UMML.py`, `UMML_core.py`, `umml_autodetect/` | Original UMML compatibility layer and reusable upstream-derived behavior |
| `umml_runtime/`, `runtime_bridge/` | Optional experimental runtime protocol, kept outside ordinary mod deployment |

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

Windows contributors can use the equivalent PowerShell virtual-environment activation and run the same Python checks. Native Windows packaging is validated in its own workflow.

## Contributing

Mod-manager improvements, creator tools, asset-analysis workflows, provider adapters, package manifests, UI/UX work, documentation, and synthetic tests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md).

Do not commit copyrighted game assets, decrypted metadata, personal roster data, downloaded mods without redistribution permission, credentials, or generated packages.

The most valuable contributions are often unglamorous:

- document a real package layout;
- provide a redistributable synthetic fixture reproducing a failure;
- improve character/dress/part detection without inventing certainty;
- remove an unexplained creator step;
- replace a legacy editor with a tested native workflow;
- add compatibility metadata to a mod;
- improve an external-tool adapter while preserving provenance and licensing.

## Lineage and legal status

Uma Mod Manager is forked from and preserves the work of **UMML / UmaMusume Mod Loader** and its contributors. The existing MIT license and copyright notice remain intact. New project contributions are made under the same repository license unless stated otherwise.

Third-party mods, extractors, viewers, libraries, and community tools retain their original authorship and licenses. See [NOTICE.md](NOTICE.md).

This project is not affiliated with Cygames. Do not distribute copyrighted game assets or decrypted game databases through this repository.

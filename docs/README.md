# Documentation index

This repository contains two separately packaged desktop applications and one optional runtime experiment. Start with the document for the component you are actually changing. Humanity has already invented enough accidental coupling.

## Users

| Document | Purpose |
| --- | --- |
| [`../README.md`](../README.md) | Repository overview, DEB/AppImage downloads, installation, and product comparison |
| [`../MANAGER_README.md`](../MANAGER_README.md) | Complete UMML Manager user guide, package formats, profiles, conflicts, recovery, and CLI |
| [`MANAGER_MOD_MANIFEST.md`](MANAGER_MOD_MANIFEST.md) | Creator metadata, profile-scoped option groups, path rules, and configurable-package validation |
| [`MANAGER_THEMES.md`](MANAGER_THEMES.md) | Persistent Light/System/Dark behavior, desktop detection, widget coverage, and package smoke tests |
| [`LINUX.md`](LINUX.md) | Linux port details and source-install notes |
| [`AUTODETECTION.md`](AUTODETECTION.md) | Steam, Proton, Wine-prefix, and Persistent-data discovery |
| [`PACKAGING.md`](PACKAGING.md) | Shared frozen runtime, separate DEB/AppImage builds, validation, and source-install boundaries |

## Contributors

| Document | Purpose |
| --- | --- |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Contribution rules, required checks, fixtures, and review expectations |
| [`MANAGER_ARCHITECTURE.md`](MANAGER_ARCHITECTURE.md) | Manager library, resolver, deployment engine, providers, and safety boundaries |
| [`MANAGER_BSTAR_REVIEW.md`](MANAGER_BSTAR_REVIEW.md) | Comparative product and architecture review, adopted ideas, rejected patterns, and future acceptance rules |
| [`MANAGER_DEVELOPMENT.md`](MANAGER_DEVELOPMENT.md) | Manager setup, tests, debugging, and extension guidance |
| [`MANAGER_MAIN_PROMOTION.md`](MANAGER_MAIN_PROMOTION.md) | Exact code, CI, package, and Bazzite evidence required before merging the Manager preview into `main` |
| [`MANAGER_RELEASE_CHECKLIST.md`](MANAGER_RELEASE_CHECKLIST.md) | Real-machine gates before publishing stable DEB/AppImage manager packages |
| [`RUNTIME_BRIDGE.md`](RUNTIME_BRIDGE.md) | Optional fail-closed protocol and the boundary around in-game adapters |
| [`../SECURITY.md`](../SECURITY.md) | Security reporting and sensitive-data handling |

## Product boundaries

- **Legacy UMML** owns one-folder loading, preview, backup, restore, platform discovery, and upstream-derived tools.
- **UMML Manager** owns the immutable library, profiles, load order, providers, conflict planning, editing workspace, transactional deployment, and its DEB/AppImage packaging.
- **Runtime bridge** is optional and separately reviewed. It is not included in either manager package and must not make unsupported game builds attempt hooks.

Generated packages, AppDirs, user state, game data, decrypted metadata, downloaded tools, and mod archives do not belong in source control.

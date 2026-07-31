# UMML-Manager documentation

UMML-Manager is now the repository's primary product. The original UMML loader and editors remain as a compatibility layer while native Manager workflows replace them without dropping working features.

Start with the document matching what you are trying to do. Reading every architecture note before installing one pink costume remains optional, despite what software repositories seem to imply.

## Start here

| Document | Audience | Purpose |
| --- | --- | --- |
| [`../README.md`](../README.md) | Everyone | Project identity, features, downloads, workflows, layout, and status |
| [`PROJECT_VISION.md`](PROJECT_VISION.md) | Everyone | Mission, audiences, product pillars, priorities, non-goals, and definition of success |
| [`../MANAGER_README.md`](../MANAGER_README.md) | Players | Installation, interface, automatic preparation, profiles, deployment, recovery, and CLI |
| [`MOD_CREATOR_GUIDE.md`](MOD_CREATOR_GUIDE.md) | Mod creators | Workspace, targeting, options, compatibility, validation, testing, and publishing workflow |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Contributors | Repository boundaries, development checks, safety rules, fixtures, and review requirements |

## Player and creator references

| Document | Purpose |
| --- | --- |
| [`MANAGER_MOD_MANIFEST.md`](MANAGER_MOD_MANIFEST.md) | Package identity, targets, compatibility policy, option groups, include patterns, and validation |
| [`MANAGER_THEMES.md`](MANAGER_THEMES.md) | Persistent Light/System/Dark behavior and package smoke tests |
| [`AUTODETECTION.md`](AUTODETECTION.md) | Steam, Proton, Wine-prefix, and Persistent-data discovery |
| [`LINUX.md`](LINUX.md) | Linux compatibility and source-install notes |
| [`UMAEXTRACTOR_INTEGRATION.md`](UMAEXTRACTOR_INTEGRATION.md) | Veteran-data provider lineage, formats, privacy, licensing, and process boundaries |

## Architecture and development

| Document | Purpose |
| --- | --- |
| [`MANAGER_ARCHITECTURE.md`](MANAGER_ARCHITECTURE.md) | Library, profiles, resolver, preparation, deployment, providers, state, and safety boundaries |
| [`MANAGER_DEVELOPMENT.md`](MANAGER_DEVELOPMENT.md) | Development environment, tests, debugging, extension points, and fixtures |
| [`MANAGER_AUDIT.md`](MANAGER_AUDIT.md) | Source and package audit results, known risks, and evidence |
| [`MANAGER_BSTAR_REVIEW.md`](MANAGER_BSTAR_REVIEW.md) | Blue Star Manager comparison, adopted product ideas, rejected implementation patterns, and acceptance rules |
| [`MANAGER_FEATURE_ROADMAP.md`](MANAGER_FEATURE_ROADMAP.md) | Planned player, creator, provider, backend, Studio, runtime, and polish work |
| [`RUNTIME_BRIDGE.md`](RUNTIME_BRIDGE.md) | Optional fail-closed runtime protocol and adapter boundary |

## Packaging and release

| Document | Purpose |
| --- | --- |
| [`PACKAGING.md`](PACKAGING.md) | Native Windows, frozen runtime, Debian, AppImage, source-install, and artifact validation |
| [`MANAGER_MAIN_PROMOTION.md`](MANAGER_MAIN_PROMOTION.md) | Exact code, CI, package, and real-machine evidence required before promotion |
| [`MANAGER_RELEASE_CHECKLIST.md`](MANAGER_RELEASE_CHECKLIST.md) | Stable-release and destructive-recovery gates |
| [`../MANAGER_CHANGELOG.md`](../MANAGER_CHANGELOG.md) | Manager release history |
| [`../SECURITY.md`](../SECURITY.md) | Vulnerability reporting, sensitive data, archive/provider risks, and process-memory tools |

## Repository boundaries

### Primary application

`umml_manager/` owns:

- immutable mod library and versions;
- profiles and load order;
- automatic preparation and source analysis;
- provider browsing and validated imports;
- package targeting and configuration;
- conflict planning;
- transactional deployment and restoration;
- native player and creator UI;
- read-only external-data workspaces.

### Compatibility layer

The original UMML paths, including `UMML.py`, `UMML_core.py`, platform discovery, and existing editing tools, remain available through a guarded Studio host.

New features should not extend the compatibility layer merely because it is easier to add one more callback. Extract reusable logic into services and build native Manager workflows with tests and recovery behavior.

### Optional runtime work

`umml_runtime/` and `runtime_bridge/` remain separate, optional, and fail closed. They do not permit arbitrary executable plugins through ordinary mod packages.

## Files that never belong in source control

Do not commit:

- game executables or assets;
- encrypted or decrypted game databases;
- real `Persistent/dat` trees or backups;
- Wine prefixes, Steam credentials, cookies, or account identifiers;
- real veteran-roster data;
- downloaded mods without redistribution permission;
- unlicensed external tools;
- Manager libraries, profiles, baselines, recovery state, logs, or caches;
- virtual environments, AppDirs, PyInstaller work trees, DEBs, AppImages, portable ZIPs, or other generated packages.

Use synthetic, redistributable fixtures for tests and documentation.

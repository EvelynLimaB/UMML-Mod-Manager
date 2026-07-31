# Uma Mod Manager documentation

Uma Mod Manager is the repository's primary product. The original UMML loader and editors remain as a compatibility layer while native Manager workflows replace them without dropping working features.

Start with the document matching the job at hand. Reading every architecture note before installing one pink costume remains optional, despite what software repositories seem to imply.

## Start here

| Document | Audience | Purpose |
| --- | --- | --- |
| [`../README.md`](../README.md) | Everyone | Project identity, features, downloads, workflows, layout, and status |
| [`releases/0.2.0-alpha.19.md`](releases/0.2.0-alpha.19.md) | Testers | Exact alpha19 Community Test changes, priorities, known limitations, safety, and feedback |
| [`TESTING_AND_FEEDBACK.md`](TESTING_AND_FEEDBACK.md) | Testers | Exact-build evidence, player/creator test matrix, support bundles, severity, privacy, and reporting |
| [`../MANAGER_README.md`](../MANAGER_README.md) | Players | Installation, interface, automatic preparation, profiles, deployment, recovery, support bundles, and CLI |
| [`MOD_CREATOR_GUIDE.md`](MOD_CREATOR_GUIDE.md) | Mod creators | Workspace, targeting, options, compatibility, validation, testing, and publishing workflow |
| [`PROJECT_VISION.md`](PROJECT_VISION.md) | Everyone | Mission, audiences, product pillars, priorities, non-goals, and success criteria |
| [`BRANDING_AND_COMPATIBILITY.md`](BRANDING_AND_COMPATIBILITY.md) | Everyone | Public name, stable technical identifiers, data-root compatibility, and future migration rules |
| [`../NOTICE.md`](../NOTICE.md) | Everyone | Original UMML lineage, external-tool credits, licensing boundaries, and third-party notices |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | Contributors | Repository boundaries, development checks, safety rules, fixtures, testing reports, and review requirements |

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
| [`MANAGER_ARCHITECTURE.md`](MANAGER_ARCHITECTURE.md) | Library, profiles, resolver, preparation, deployment, providers, state, diagnostics, and safety boundaries |
| [`MANAGER_DEVELOPMENT.md`](MANAGER_DEVELOPMENT.md) | Development environment, tests, debugging, extension points, and fixtures |
| [`MANAGER_AUDIT.md`](MANAGER_AUDIT.md) | Source and package audit results, known risks, and evidence |
| [`MANAGER_BSTAR_REVIEW.md`](MANAGER_BSTAR_REVIEW.md) | Blue Star Manager comparison, independently adopted product ideas, rejected patterns, and acceptance rules |
| [`MANAGER_FEATURE_ROADMAP.md`](MANAGER_FEATURE_ROADMAP.md) | Planned player, creator, provider, backend, Studio, runtime, testing, and polish work |
| [`RUNTIME_BRIDGE.md`](RUNTIME_BRIDGE.md) | Optional fail-closed runtime protocol and adapter boundary |

## Packaging and release

| Document | Purpose |
| --- | --- |
| [`PACKAGING.md`](PACKAGING.md) | Native Windows, frozen runtime, Debian, AppImage, source-install, artifact validation, and Community Test payloads |
| [`RELEASE_PROCESS.md`](RELEASE_PROCESS.md) | Version forms, exact prerelease workflow, immutable artifacts, feedback loop, rollback, and promotion evidence |
| [`MANAGER_MAIN_PROMOTION.md`](MANAGER_MAIN_PROMOTION.md) | Code, CI, package, and real-machine evidence expected before major promotion |
| [`MANAGER_RELEASE_CHECKLIST.md`](MANAGER_RELEASE_CHECKLIST.md) | Stable-release, real-mod, platform, and destructive-recovery gates |
| [`../MANAGER_CHANGELOG.md`](../MANAGER_CHANGELOG.md) | Manager release history |
| [`../SECURITY.md`](../SECURITY.md) | Vulnerability reporting, sensitive data, support reports, archive/provider risks, and process-memory tools |

## Repository boundaries

### Primary application

`umml_manager/` owns the immutable mod library, profiles, automatic preparation, provider browsing, validated imports, package configuration, conflict planning, transactional deployment/restoration, native UI, creator workflows, privacy-scrubbed support reports, and read-only external-data workspaces.

### Compatibility layer

The original UMML paths, including `UMML.py`, `UMML_core.py`, platform discovery, and existing editing tools, remain available through a guarded Studio host.

New features should not extend the compatibility layer merely because adding one more callback is convenient. Extract reusable logic into services and build native Manager workflows with tests and recovery behavior.

### Optional runtime work

`umml_runtime/` and `runtime_bridge/` remain separate, optional, and fail closed. They do not permit arbitrary executable plugins through ordinary mod packages.

## Files that never belong in source control or public reports

Do not commit or attach game executables or assets, decrypted game databases, real `Persistent/dat` trees, Wine prefixes, Steam credentials, account identifiers, veteran-roster data, unlicensed external tools, downloaded mods without redistribution permission, Manager state, recovery data, virtual environments, package build trees, generated release artifacts, or unreviewed support bundles.

Use synthetic, redistributable fixtures for tests and documentation. Inspect `support-report.json` before attaching a generated support bundle to an issue.

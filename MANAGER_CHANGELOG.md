# UMML Manager changelog

## 0.2.0~alpha16 - 2026-07-29

### Configurable packages

- Added native `option_groups` metadata for single-choice and multiple-choice package variants.
- Added profile-scoped selections so profiles can choose different variants from one imported version.
- Preparation records source paths to final hashed targets without changing imported files.
- Resolution filters prepared claims by the active profile before conflict planning.
- Invalid, unknown, ambiguous, stale, or empty configuration blocks apply and appears in the plan.

### Creator workflow

- Added **Library → New package** for timestamped editable package workspaces.
- The builder creates a manifest, `assets/`, instructions, and an optional two-choice template without importing or applying it.
- Added a native configuration dialog using radio buttons for single-choice groups and checkboxes for multiple-choice groups.
- Added creator manifest documentation and a comparative manager design review.

### Validation

- Configurable manifests are validated before immutable import.
- Include patterns reject traversal, absolute paths, unmatched patterns, and files controlled by multiple choices or groups.
- Older configurable prepared caches require one explicit re-prepare to gain source-to-target mapping.
- Expanded callback auditing to the configuration and package-builder dialogs.
- Added regression coverage for manifests, defaults, profile choices, resolver filtering, blockers, imports, and package workspaces.

## 0.2.0~alpha15 - 2026-07-26

- Connected all Manager entry points and packages to fresh robust Steam and Proton discovery.
- Added scored detection evidence and package-level Mint and Debian layout regressions.
- Added persistent Light, System, and Dark appearance modes with package smoke tests.
- Fixed packaged Linux folder opening by restoring the host environment and reporting helper failures.

## 0.2.0~alpha14 - 2026-07-25

- Added package-level disposable import, deployment, restoration, and interrupted-recovery self-tests.
- Added read-only diagnostics, network smoke testing, real-profile verification on temporary copies, and native Tk page rendering.
- Expanded source, Debian, AppImage, and runtime-parity promotion gates.

## 0.2.0~alpha13 - 2026-07-23

- Added explicit all-or-nothing migration from legacy backups into Manager-owned target-bound baselines.
- Prevented modified files from becoming vanilla baselines and added actionable first-apply recovery guidance.

## 0.2.0~alpha12 - 2026-07-23

- Hardened interrupted recovery, process checks, snapshot races, and active-state verification before mutation.
- Prevented unsafe first adoption without a known baseline.
- Preserved profile installation identity and added explicit verified-target rebinding.

## 0.2.0~alpha11 - 2026-07-23

- Centralized fail-closed deployment and immutable import through guarded public boundaries.
- Enforced every resolver blocker for GUI, CLI, package tests, and compatibility callers.
- Added typed provider fallback, concurrent import serialization, and stronger diagnostics.

## 0.2.0~alpha10 - 2026-07-23

- Fixed deeply nested provider-confirmed legacy package imports.
- Synchronized controls with selection, background work, blockers, paging, metadata, and game-running state.
- Added visible browser and folder failures plus static callback auditing.

## 0.2.0~alpha9 - 2026-07-22

- Added automatic preparation after compatible imports while keeping apply explicit.
- Preserved sources after preparation failures.
- Added safe normalization for provider-confirmed loose legacy archives and rejected unsupported payloads.

## 0.2.0~alpha8 - 2026-07-22

- Fixed GameBanana installation when catalogue rows omitted full file metadata.
- Added asynchronous detail hydration, exact file selection, and an Install latest retry path.

## 0.2.0~alpha7 - 2026-07-22

- Completed preview-provider wiring and full pinned dependency coverage in Manager CI.
- Verified image support and complete Debian and AppImage runtime parity.

## 0.2.0~alpha6 - 2026-07-22

- Added architecture, input-safety, state, archive, and deployment audits and regressions.
- Added versioned state, verified transactions, target-scoped baselines, durable recovery, and tamper detection.
- Added provider and backend contracts, profile binding, dependency planning, and bounded previews.

## 0.2.0~alpha5 - 2026-07-22

- Fixed portable mandatory HTTPS trust across common Linux layouts.
- Added validated environment trust paths, bundled certificate fallback, diagnostics, and package inspection.

## 0.2.0~alpha4 - 2026-07-22

- Added an AppImage built from the same frozen runtime as the Debian package.
- Added checksums, runtime parity, bounded extraction, and pinned packaging tools.

## 0.2.0~alpha3 - 2026-07-21

- Separated application files from persistent Manager data and stopped stale launchers from shadowing packages.
- Hardened profiles, critical state, version coexistence, selection, and uninstall preservation.

## 0.2.0~alpha2 - 2026-07-21

- Added first-launch installation detection and automatic readable-metadata preparation.
- Added guided installation settings.

## 0.2.0~alpha1 - 2026-07-21

- Added Library, Discover, Studio, Conflicts, and Settings pages.
- Added provider browsing, local discovery, editable workspaces, Studio compatibility, and CLI tools.

## 0.1.0~alpha1 - 2026-07-21

- Initial separately packaged Manager foundation with immutable library records, profiles, conflict planning, verified deployment, baselines, local and provider import, GUI, CLI, tests, and Debian packaging.

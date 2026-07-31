## Scope

- Area: <!-- player UX, creator tooling, provider, preparation, resolver, deployment, compatibility Studio, runtime, packaging, docs -->
- Platforms: <!-- Windows, Linux, Steam, Proton, Global, Japan, DMM, etc. -->
- Package formats: <!-- source, Windows portable, DEB, AppImage -->

## Problem

<!-- Describe the current limitation with reproducible steps. Explain who is affected: player, creator, maintainer, or external-tool developer. -->

## Changes

<!-- Explain the implementation, why it belongs in this layer, and how it improves normal play or mod development. -->

## User experience

- [ ] Ordinary use does not require manual preparation, re-preparation, file renaming, hash copying, or JSON editing.
- [ ] New windows are parented, focused, and usable at supported sizes.
- [ ] Automatic work exposes progress and actionable failure states.
- [ ] Detected characters, dresses, parts, and content types distinguish evidence from inference.
- [ ] Player and creator documentation match the actual workflow.

## Safety and compatibility

- [ ] No game assets, decrypted databases, user paths, credentials, roster data, or unlicensed external binaries are included.
- [ ] Imported source versions remain immutable.
- [ ] Preparation and source analysis never write game files.
- [ ] Game-file mutations remain blocked while the game is running.
- [ ] Existing stored state remains compatible or includes an explicit migration.
- [ ] Archive, provider, manifest, and external-tool inputs remain untrusted.
- [ ] Apply and restore still use the guarded resolver and transactional deployment engine.
- [ ] External tools retain project, author, source, version, and license provenance.
- [ ] Runtime work fails closed on unknown game builds.

## Validation

<!-- Check only what applies and include exact commands, run links, package hashes, and real-machine evidence. -->

- [ ] `python scripts/audit_manager.py`
- [ ] `bash scripts/check_manager.sh`
- [ ] `bash scripts/check_legacy.sh`
- [ ] Runtime Python tests
- [ ] `cargo test --manifest-path runtime_bridge/Cargo.toml`
- [ ] Source GUI rendered in Light and Dark modes
- [ ] Native Windows portable built and tested
- [ ] Frozen Linux runtime built
- [ ] Debian package built and inspected
- [ ] AppImage built and inspected
- [ ] Real mod or creator-workflow smoke test
- [ ] Apply, profile switch, and vanilla restoration tested

## State and migration impact

<!-- Describe new fields, defaults, migrations, cache invalidation, package re-analysis, or why no state change occurs. -->

## External projects and credits

<!-- List every external project, author, source URL, revision/version, license, bundled status, and modification. “Credited” is not the same as “licensed for redistribution.” -->

## Not tested

<!-- State unavailable platforms, providers, game builds, package layouts, recovery cases, and hardware honestly. -->

## Release impact

- [ ] No release-note change needed
- [ ] `MANAGER_VERSION`, changelog, README, and AppStream metadata updated
- [ ] Packaging or workflow artifact names updated
- [ ] Real-machine gates added to the release checklist

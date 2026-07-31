## Scope

- Area: <!-- player UX, creator tooling, provider, preparation, resolver, deployment, diagnostics/support reports, compatibility Studio, runtime, packaging, release, docs -->
- Platforms: <!-- Windows, Linux, Steam, Proton, Global, Japan, DMM, etc. -->
- Package formats: <!-- source, Windows portable, DEB, AppImage -->
- Exact head: <!-- full commit SHA after the final change -->

## Problem

<!-- Describe the current limitation with reproducible steps. Explain who is affected: player, creator, tester, maintainer, or external-tool developer. -->

## Changes

<!-- Explain the implementation, why it belongs in this layer, and how it improves normal play, mod development, testing, or recovery. -->

## User experience

- [ ] Ordinary use does not require manual preparation, re-preparation, file renaming, hash copying, or JSON editing.
- [ ] New windows are parented, focused, and usable at supported sizes.
- [ ] Automatic work exposes progress and actionable failure states.
- [ ] Detected characters, dresses, parts, and content types distinguish evidence from inference.
- [ ] Errors identify the next safe action instead of exposing internal maintenance terms.
- [ ] Player, creator, testing, and release documentation match the actual workflow.

## Safety, privacy, and compatibility

- [ ] No game assets, decrypted databases, user paths, credentials, roster data, raw support reports, or unlicensed external binaries are included.
- [ ] Imported source versions remain immutable.
- [ ] Preparation and source analysis never write game files.
- [ ] Game-file mutations remain blocked while the game is running or process state is uncertain.
- [ ] Existing stored state remains compatible or includes an explicit migration and rollback.
- [ ] Archive, provider, manifest, diagnostic, and external-tool inputs remain untrusted.
- [ ] Apply and restore still use the guarded resolver and transactional deployment engine.
- [ ] Recovery evidence is preserved when a failure cannot be repaired safely.
- [ ] External tools retain project, author, source, version, and license provenance.
- [ ] Runtime work fails closed on unknown game builds.
- [ ] Support-bundle changes preserve data minimization, redaction, path containment, bounded output, and inspect-before-upload guidance.
- [ ] Public-name changes preserve technical package, command, desktop-ID, artifact, and data-root compatibility unless an explicit migration is included.

## Validation

<!-- Check only what applies. Include exact commands, run links, artifact filenames, SHA-256 values, and real-machine evidence. Evidence belongs to the final exact head. -->

- [ ] `python scripts/audit_manager.py`
- [ ] `python scripts/audit_branding.py`
- [ ] `python scripts/audit_release.py`
- [ ] `bash scripts/check_manager.sh`
- [ ] `bash scripts/check_legacy.sh`
- [ ] Runtime Python tests
- [ ] `cargo test --manifest-path runtime_bridge/Cargo.toml`
- [ ] Source GUI rendered in Light and Dark modes
- [ ] Native Windows portable built and tested
- [ ] Frozen Linux runtime built
- [ ] Debian package built, installed, removed, and state preservation verified
- [ ] AppImage built and inspected
- [ ] Finished packages contain exact tester/release documents
- [ ] Support bundle generated and manually inspected using synthetic or disposable data
- [ ] Real mod or creator-workflow smoke test
- [ ] Apply, profile switch, vanilla restoration, and application rollback tested
- [ ] Successful and failed test outcomes recorded where relevant

## State and migration impact

<!-- Describe new fields, defaults, migrations, cache invalidation, package re-analysis, technical identifier changes, or why no state change occurs. -->

## Failure and rollback behavior

<!-- Explain what remains unchanged after failure, what recovery evidence exists, how a user returns to the previous application package, and which actions require expendable or independently backed-up game data. -->

## External projects and credits

<!-- List every external project, author, source URL, revision/version, license, bundled status, and modification. “Credited” is not the same as “licensed for redistribution.” -->

## Not tested

<!-- State unavailable platforms, providers, game builds, package layouts, recovery phases, services, hardware, and privacy corpora honestly. Empty evidence is not a pass. -->

## Release impact

- [ ] No release-note change needed
- [ ] `MANAGER_VERSION`, changelog, README, player guide, citation, and AppStream metadata updated
- [ ] Versioned `docs/releases/` notes and Testing feedback guidance updated
- [ ] Release audit and tests updated for new metadata
- [ ] Packaging payloads or workflow artifact names updated
- [ ] Manual Community Test workflow exercised with publication disabled
- [ ] Exact artifacts and checksums independently verified
- [ ] Real-machine gates added to the release checklist
- [ ] Published artifacts remain immutable; changed binaries use a new version/tag

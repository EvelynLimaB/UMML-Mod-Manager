# Uma Mod Manager release checklist

This checklist separates three claims that software projects routinely blur until users are debugging the difference:

1. **Build candidate:** CI produced internally consistent packages.
2. **Community Test:** exact prerelease artifacts are available for structured feedback.
3. **Stable release:** the applicable real-machine, real-mod, recovery, upgrade, and service gates passed.

A merge to `main`, a green workflow, or a Community Test prerelease does not by itself claim stability.

## Exact candidate identity

Record before testing:

- [ ] commit SHA;
- [ ] `MANAGER_VERSION`;
- [ ] portable version and Git tag;
- [ ] Windows ZIP filename and SHA-256;
- [ ] Debian filename and SHA-256;
- [ ] AppImage filename and SHA-256;
- [ ] workflow run URLs;
- [ ] versioned release-notes path;
- [ ] known exclusions.

For the current prepared campaign:

```text
MANAGER_VERSION: 0.2.0~alpha19
Portable:        0.2.0-alpha.19
Tag:             v0.2.0-alpha.19
```

## Automated candidate gates

All are required for a build candidate.

### Source and architecture

- [x] Compile every Manager Python file and packaged entry point.
- [x] Run the structural, layering, dangerous-call, duplicate-definition, and visible-button audit.
- [x] Run the public-branding and compatibility-identifier audit.
- [x] Run the exact release metadata audit.
- [x] Install pinned runtime and build dependencies and run `pip check`.
- [x] Run all `test_manager*.py` regressions on Linux and Windows.
- [x] Render every native page in Light and Dark themes from source and packaged runtimes.
- [x] Reject mutable or malformed critical state instead of silently resetting it.
- [x] Preserve settings recovery separately from critical deployment state.

### Import, preparation, profiles, and providers

- [x] Bound archive paths, links, entry counts, name lengths, and uncompressed size.
- [x] Keep imported versions immutable and serialize concurrent registry/profile updates.
- [x] Prepare compatible imports automatically without a visible Prepare/Re-prepare workflow.
- [x] Preserve imported source and the prior verified cache after preparation failure.
- [x] Support one source bundle owning multiple final targets.
- [x] Enforce profile-scoped options, dependencies, incompatibilities, region, and relative load order.
- [x] Keep providers download/import-only and retain source URL/file/hash/size/time provenance.
- [x] Reject unsupported self-installing executable patches through the generic importer.
- [x] Validate Veteran roster shape and scrub known account fields before snapshot storage.

### Deployment and recovery

- [x] Resolve every blocker before mutation begins.
- [x] Require verified, target-bound vanilla baselines.
- [x] Block writes while the game runs or process inspection is uncertain.
- [x] Use durable journals, captured snapshots, hash verification, rollback, and recovery.
- [x] Re-check live ownership and external changes immediately before mutation.
- [x] Preserve recovery evidence when recovery cannot proceed safely.
- [x] Exercise disposable import, Apply, switch, restore, external-change, migration, and interrupted-recovery paths through the packaged CLI.

### Tester support and privacy

- [x] Expose **Settings → Create support bundle**.
- [x] Include version/platform, configuration-presence, bounded library/profile summaries, and read-only diagnostics.
- [x] Exclude game assets, mod payloads, downloaded archives, baselines, transaction contents, roster snapshots, and raw settings.
- [x] Redact known paths, viewer/account names and IDs, credentials, tokens, cookies, and authorization fields.
- [x] Reject directory and symlink support-bundle destinations.
- [x] Bound long free-form text.
- [x] Ship tester guidance and release notes in every package format.

### Finished packages

- [x] Build one frozen runtime shared by Debian and AppImage.
- [x] Build the native Windows portable runtime on Windows.
- [x] Verify exact filenames, package version, architecture, and tag conversion.
- [x] Run version, CLI self-test, autodetection fixture, and GUI theme smoke against finished packages.
- [x] Compare frozen runtime trees across Debian and AppImage.
- [x] Verify certifi CA data and Pillow native imaging support.
- [x] Validate desktop and AppStream metadata.
- [x] Install and remove the Debian package in CI while preserving user data.
- [x] Generate and verify external SHA-256 files.
- [x] Refuse silently replacing artifacts under an existing Community Test tag.

## Community Test publication gates

Required before publishing a GitHub prerelease:

- [ ] Exact-head Linux and Windows workflows passed.
- [ ] `python scripts/audit_release.py --tag <tag>` passed.
- [ ] The manual testing-release workflow completed once with publication disabled.
- [ ] Downloaded workflow artifacts independently match their checksums.
- [ ] Windows portable launched on a real Windows machine without development Python.
- [ ] At least one exact Linux package launched on a real desktop.
- [ ] Settings, diagnostics, and support-bundle creation worked on those machines.
- [ ] Release notes list current limitations and do not imply stable support.
- [ ] The structured Testing feedback form is available.
- [ ] Previous package artifacts remain available for rollback.

Publication must use `--prerelease`. Do not mark a Community Test as the latest stable release.

## Community Test matrix

Use [TESTING_AND_FEEDBACK.md](TESTING_AND_FEEDBACK.md) for detailed instructions. Record passes as well as failures.

### Installation and upgrade

- [ ] Windows portable launches without Python and folder-opening actions work.
- [ ] Debian upgrades from the previous alpha without losing library, profiles, settings, baselines, journals, or workspaces.
- [ ] AppImage and Debian see the same XDG Manager data.
- [ ] Application rollback preserves all external Manager data.
- [ ] System, Light, and Dark themes persist after restart.
- [ ] Manager-owned windows open centered, raised, and focused.

### Real package corpus

- [ ] Import and prepare a normal hash-addressed ZIP.
- [ ] Import and prepare an extracted-folder package.
- [ ] Import a deeply nested loose legacy package.
- [ ] Import a package where one source bundle maps to several final targets.
- [ ] Confirm an individual preparation failure does not stop unrelated packages.
- [ ] Confirm imported source bytes remain unchanged.
- [ ] Confirm unsupported Hachimi-only or executable-patch layouts fail clearly and safely.

### Profiles and planning

- [ ] Create, enable, disable, and reorder a profile.
- [ ] Select different authored variants from one package in two profiles.
- [ ] Verify exact conflict winner follows load order.
- [ ] Verify dependency, incompatibility, region, stale metadata, and invalid-option blockers.
- [ ] Switch among at least three profiles without stale target ownership.

### Apply, switch, restore, and recovery

Use expendable or independently backed-up game data.

- [ ] Apply two non-conflicting mods.
- [ ] Apply overlapping mods and verify the planned winner.
- [ ] Switch profiles and verify removed targets restore correctly.
- [ ] Restore exact vanilla bytes from a trusted baseline.
- [ ] Change an active file externally and verify normal deployment refuses it.
- [ ] Interrupt a disposable deployment and verify recovery evidence remains complete.
- [ ] Exercise explicit force recovery only with a documented expected ownership result.

### Creator workflow

- [ ] Create a new package workspace.
- [ ] Open **Inspect & edit** and verify focus.
- [ ] Review source bundles, final targets, likely types/parts, characters, and dresses.
- [ ] Correct identity and compatibility metadata without JSON.
- [ ] Generate optional components or mutually exclusive variants.
- [ ] Import the workspace as a new immutable version.
- [ ] Confirm older versions remain intact and selectable.
- [ ] Test Apply, switch, and vanilla restoration before publishing the mod.

### Services and read-only data

- [ ] Browse and download current GameBanana files from Windows, Debian, and AppImage packages.
- [ ] Verify current preview hosts, MIME handling, redirects, and stale-selection protection.
- [ ] Import real classic `data.json` and Werseter `trained_chara_data.json` Veteran samples.
- [ ] Reject unrelated support-card, trophy, friend, card, and replay JSON.
- [ ] Inspect a support bundle manually for usefulness and privacy.

## Stable-release gates

All applicable items below must pass or be explicitly excluded with justification.

### Platform coverage

- [ ] Native Windows launch, detection, game-running guard, Apply/restore, upgrade, and rollback.
- [ ] Bazzite/KDE AppImage launch, GameBanana, previews, folders, themes, Apply/restore, and rollback.
- [ ] Mint/Debian DEB install, upgrade, removal preservation, desktop menu, Apply/restore, and rollback.
- [ ] A second supported Linux distribution.
- [ ] Multiple Steam libraries and separate game/Proton-prefix libraries.
- [ ] Machines with both Global and Japan installations.
- [ ] Native/DMM/Wine layouts claimed by documentation.

### Game updates and long-lived state

- [ ] Test after a game update replaces metadata and assets.
- [ ] Verify preparation invalidates or rebuilds against changed metadata.
- [ ] Verify a game update cannot silently replace a trusted baseline.
- [ ] Verify old active state cannot be applied to a different installation.
- [ ] Verify corrupt library, profile, baseline, active, and journal documents fail closed with actionable diagnostics.

### Provider and format claims

- [ ] Test multiple current GameBanana submissions and file-order edge cases.
- [ ] Verify failed download/extraction leaves no importable partial record.
- [ ] Add and test 7z/RAR before advertising those formats.
- [ ] Add native Hachimi deployment or clearly keep Hachimi-only packages non-deployable.
- [ ] Verify third-party credits and license status remain visible.

### Distribution and security

- [ ] Signed release artifacts or a documented signing strategy.
- [ ] Signed or authenticated update metadata before automatic updates.
- [ ] Private vulnerability-reporting path verified.
- [ ] Support-bundle privacy reviewed against a broader real corpus.
- [ ] No injector, arbitrary executable plugin, or Unity hook bundled in ordinary packages.
- [ ] Unknown game builds expose zero unsupported runtime features.

## Campaign closeout

Before promoting or replacing a Community Test, publish a summary containing:

- exact commit, artifacts, and checksums;
- automated workflow evidence;
- successful platform/package passes;
- tested mod layouts;
- Apply/switch/restore and rollback evidence;
- open critical/high failures;
- medium/low UX and documentation findings;
- deferred and untested gates;
- the next build or promotion decision.

The absence of reports is not a pass. It is an empty dataset wearing confidence as a hat.

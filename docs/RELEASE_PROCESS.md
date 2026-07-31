# Release process

Uma Mod Manager uses evidence-based prereleases. A build is not promoted because it compiled, looked plausible in one screenshot, or survived being opened by its author.

## Version forms

The same testing version appears in three deliberate forms:

| Purpose | Example |
| --- | --- |
| Debian and `MANAGER_VERSION` | `0.2.0~alpha19` |
| Portable/AppStream display | `0.2.0-alpha.19` |
| Git tag | `v0.2.0-alpha.19` |

The `~` keeps Debian prereleases ordered below a future `0.2.0`. Portable filenames and Git tags use the clearer dotted prerelease form.

The current prepared tag is **v0.2.0-alpha.19**.

## Release channels

### Workflow artifact

Every qualifying pull request and push to `main` produces short-lived CI artifacts. These are suitable for maintainers and targeted verification but may expire.

### Community Test prerelease

A GitHub prerelease keeps exact Windows portable, Debian, and AppImage artifacts available while a named testing campaign gathers feedback. It includes release notes, combined SHA-256 checksums, and a link to the tester guide.

### Stable release

A stable release requires the applicable automated, real-machine, real-mod, recovery, platform, and documentation gates. An alpha or Community Test does not silently become stable because enough time passed and everyone became tired.

## Preparing a Community Test

1. Create or select a release-preparation branch.
2. Update `MANAGER_VERSION`.
3. Add the top changelog section.
4. Add `docs/releases/<portable-version>.md`.
5. Update README and player-guide status text.
6. Add the matching AppStream release entry.
7. Run:

   ```bash
   python scripts/audit_release.py --tag v0.2.0-alpha.19
   bash scripts/check_manager.sh
   ```

8. Confirm Windows and Linux package workflows pass at the exact head.
9. Perform at least one real launch on Windows and one real launch using either the Debian package or AppImage.
10. Run the manual **Uma Mod Manager testing release** workflow with `publish_release` disabled first.
11. Download the workflow artifacts and verify the combined checksums independently.
12. Re-run the same workflow with `publish_release` enabled only for the already validated exact commit and tag.

## Manual release workflow

The workflow `.github/workflows/manager-testing-release.yml` accepts:

- `release_tag`: must exactly match `MANAGER_VERSION` after conversion;
- `publish_release`: builds only when false, builds and publishes a GitHub prerelease when true.

The workflow:

- audits version and release metadata;
- runs Manager regressions on Linux and Windows;
- builds the Windows portable package;
- builds the Debian package and AppImage;
- exercises packaged self-tests and GUI smokes;
- creates platform checksums and a combined `SHA256SUMS`;
- uploads build artifacts even when publication is disabled;
- publishes with `gh release create --prerelease` only after all jobs pass.

It never marks a Community Test as the latest stable release.

## Tester feedback loop

For each testing release:

1. Open a tracking issue or discussion summarizing the test matrix.
2. Link the exact release, checksums, release notes, and tester guide.
3. Ask testers to use the structured **Testing feedback** form.
4. Record successful passes as evidence, not merely failures.
5. Triage reports by safety impact and reproducibility.
6. Convert reusable failures into synthetic fixtures where licensing permits.
7. Publish a replacement prerelease when binaries change. Never silently replace an artifact under the same checksum.
8. Close the campaign with a summary of passed, failed, deferred, and untested gates.

## Artifact immutability

A published artifact is identified by all of:

- release tag;
- commit SHA;
- filename;
- SHA-256.

When code or packaging changes, increment the release version or testing iteration and publish new artifacts. Do not overwrite a file while pretending it remains the same build. Humans already have enough trouble reporting what they downloaded without the binary changing underneath them.

## Rollback

A testing release must preserve a practical rollback path:

- Windows portable users keep the previous extracted application folder.
- Debian users keep the previous `.deb` and can reinstall it explicitly.
- AppImage users keep the previous file.
- Manager user data remains outside application packages.
- Technical package, command, desktop ID, and data-root identifiers remain stable during the compatibility window.
- A rollback must not delete the library, profiles, settings, workspaces, baselines, or recovery journals.

Rollback does not mean restoring game files from an unknown state. Use Uma Mod Manager's verified Restore/Apply engine and trusted baselines for game data.

## Promotion evidence

A release-campaign summary should include:

- exact commit and artifact hashes;
- automated workflow links;
- platform/package matrix;
- successful real-machine passes;
- tested mod layouts;
- apply/switch/restore evidence;
- upgrade and rollback evidence;
- unresolved safety or compatibility failures;
- documentation mismatches;
- explicit exclusions.

The detailed stable checklist remains in [MANAGER_RELEASE_CHECKLIST.md](MANAGER_RELEASE_CHECKLIST.md).

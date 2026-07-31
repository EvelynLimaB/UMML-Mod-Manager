# Testing and feedback

Uma Mod Manager testing releases exist to collect useful evidence before a build is promoted. They are not stable releases with a more adventurous filename.

The current testing line is **0.2.0~alpha19 / 0.2.0-alpha.19**.

## Before testing

1. Read the release notes for the exact build.
2. Verify the downloaded file with the published SHA-256 checksum.
3. Keep the game closed for Apply, restore, baseline, recovery, and legacy Studio operations.
4. Keep an independent backup of important game and Manager data.
5. Do not test destructive recovery on the only copy of data you care about.
6. Record the exact artifact, operating system, game region, and package format.

The technical package and data identifiers remain `umml-manager` for upgrade compatibility. Do not delete the Manager data root merely because the public application name changed.

## Exact build information

A useful report identifies the build precisely. Include:

- `MANAGER_VERSION` shown by the application or `umml-manager-cli --version`;
- package format: Windows portable, Debian package, AppImage, or source;
- artifact filename and SHA-256;
- operating system and desktop environment;
- native Windows, Proton, Wine, DMM, or another game layout;
- game region;
- whether this was a clean installation or an upgrade;
- the previous Manager version when upgrading.

A report that says “latest” becomes historical fiction as soon as another build exists.

## What to test

### Installation and upgrades

- Launch the Windows portable build without a development Python installation.
- Install the Debian package over an earlier alpha and confirm the same library, profiles, settings, baselines, and workspaces remain.
- Launch the AppImage and confirm it sees the same XDG Manager data as the Debian package.
- Change between System, Light, and Dark themes and restart.
- Open Manager data and workspaces through the UI.

### Detection and normal play

- Auto-detect the intended game installation.
- Confirm region, game directory, `Persistent/dat`, and readable metadata are correct.
- Launch and close the game, then confirm the game-status badge changes correctly.
- Confirm Apply and write-capable Studio actions remain blocked while the game is running.
- Run diagnostics after game or metadata updates.

### Import and automatic preparation

- Import a ZIP and an extracted mod folder.
- Import a deeply nested legacy package.
- Confirm preparation starts automatically and no manual Prepare or Re-prepare action is required.
- Confirm one failed mod does not stop unrelated packages from preparing.
- Confirm the imported source remains unchanged after preparation and profile switching.
- Report the package source URL and file ID when redistribution permits linking to it. Do not upload the mod itself without permission.

### Profiles, options, and conflicts

- Enable and disable mods in a profile.
- Move enabled mods up and down.
- Configure package variants in two profiles and confirm each profile keeps its own selection.
- Test overlapping mods and confirm the displayed winner follows load order.
- Confirm missing dependencies, incompatibilities, region mismatches, stale preparation, or invalid options block Apply with a useful explanation.

### Apply, switch, and restore

Use expendable or independently backed-up game data.

- Apply one profile and verify expected files.
- Switch to a second profile.
- Restore vanilla.
- Confirm exact original bytes return where a trusted baseline exists.
- Change a managed file externally and confirm normal deployment refuses to overwrite unknown state.
- Do not use force recovery casually. Record the exact reason and expected ownership result when testing it.

### Creator workflow

- Create a package workspace.
- Use **Inspect & edit** on an imported package.
- Confirm the window opens in focus.
- Review detected source bundles, final targets, content types, parts, character IDs, and dress IDs.
- Correct compatibility metadata and create profile options without editing JSON.
- Save and import as a new immutable version.
- Confirm old and new versions do not overwrite one another.
- Test the package in a dedicated profile before publishing it.

### Veteran data

- Import classic `data.json` and Werseter `trained_chara_data.json` samples.
- Confirm unrelated support-card, trophy, friend, or replay JSON is rejected as a Veteran roster.
- Confirm known viewer/account fields are removed before the snapshot is stored.
- Check sorting, searching, details, and CSV export.
- Treat borrowed or transient memory-derived records as uncertain unless independently verified.

## Create a support bundle

Open **Settings → Create support bundle**.

The generated ZIP contains a privacy-scrubbed `support-report.json` with:

- Manager version and runtime information;
- operating-system information;
- configuration-presence flags rather than raw settings;
- high-level mod and profile summaries;
- read-only diagnostic results;
- warnings encountered while collecting the report.

It intentionally excludes game assets, mod payloads, downloaded archives, vanilla baselines, transaction contents, Veteran roster snapshots, raw settings, credentials, and known account identifiers.

Inspect `support-report.json` before uploading it. Custom mod names and free-form error messages may still contain text you consider private.

## How to report feedback

Use the **Testing feedback** issue form for successful, partial, or failed test passes. Use **Bug report** when there is a reproducible defect not tied to a specific testing campaign. Use **Mod compatibility** for one package that imports, prepares, resolves, or deploys incorrectly.

A strong report includes:

1. Exact build and SHA-256.
2. Environment and installation layout.
3. Starting state, including upgrade history.
4. Numbered reproduction steps.
5. Expected and actual results.
6. Whether game or Manager files changed.
7. A support bundle.
8. Screenshots only when they show state that text cannot express clearly.
9. Links to third-party mods, not unauthorized copies.

Do not attach copyrighted game files, decrypted game databases, private roster dumps, access tokens, credentials, or third-party mods without redistribution permission.

## Severity guide

- **Critical:** trusted vanilla data can be lost or corrupted, recovery evidence is destroyed, or writes occur against the wrong installation.
- **High:** Apply/restore is incorrect, a safety blocker can be bypassed, or an upgrade loses Manager state.
- **Medium:** an important workflow fails but preserves data and has a practical workaround.
- **Low:** visual, wording, discoverability, focus, layout, or minor compatibility problems.
- **Suggestion:** a workflow works but could require fewer steps or explain itself better.

## Successful tests matter

Reports that a workflow passed on a particular package and platform are valuable. Include the exact build, package format, environment, and test area. This creates evidence for promotion instead of leaving maintainers to infer success from silence, humanity's favourite and least informative monitoring protocol.

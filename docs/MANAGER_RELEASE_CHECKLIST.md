# UMML Manager release checklist

This is the stable Manager release checklist. Merging the alpha preview into `main` does not claim these larger real-game, destructive-recovery, platform, and corpus gates are complete. PR #2 follows the smaller, explicit [main-promotion gate](MANAGER_MAIN_PROMOTION.md); stable DEB/AppImage release advertising still requires every applicable item below to pass or be explicitly excluded.

## Automated verification

- [x] Compile every manager Python file.
- [x] Run the structural AST and architecture audit.
- [x] Audit every visible Tk button callback against ManagerGUI and its action mixins.
- [x] Install the complete pinned runtime dependency set before manager regressions.
- [x] Verify the default provider registry uses the preview-aware GameBanana client.
- [x] Exercise preview URL normalization, host/redirect restrictions, MIME handling, byte limits, pixel limits, malformed images, and provider wiring.
- [x] Exercise selection, busy-task, paging, blocker, game-running, unknown-status, Studio-host, and Settings target-edit button states headlessly.
- [x] Verify changed GameBanana region/sort/query starts from page 1 and stale availability is restored after tasks.
- [x] Verify typed target path or region changes revoke stale installation verification while detected targets retain it.
- [x] Verify recovery checks the game before rollback and preserves journals when process inspection fails or the game starts between checks.
- [x] Verify active ownership and live targets still match captured snapshots immediately before mutation.
- [x] Refuse first-time ownership of an already matching mod file when no vanilla baseline exists.
- [x] Migrate a complete legacy `dat.backup` set explicitly, preserve the old backups, and reject incomplete migration without partial baselines.
- [x] Preserve prepared state across identical immutable re-imports and preserve profile bindings across enable/reorder edits.
- [x] Reject implicitly saved metadata without a recorded fingerprint and distinguish auto-detected saves from later manual edits.
- [x] Audit the source installer for the complete Manager, auto-detection, and legacy Studio runtime payload.
- [x] Build one frozen runtime and compare it against complete DEB/AppImage runtime trees.
- [x] Verify bundled certifi data and Pillow's compiled imaging extension in both packages.
- [x] Exercise disposable import, conflict, apply, switch, restore, external-change, legacy-migration, and interrupted-recovery paths through the packaged CLI.
- [x] Render every native Manager page against disposable state from source, the frozen runtime, the DEB payload, the installed DEB, and the AppImage under Xvfb.
- [x] Exercise historical source-install migration plus install/uninstall state preservation in an isolated XDG home.
- [x] Install and remove the real Debian package in CI while verifying Manager user data survives.
- [x] Configure the Manager workflow to run for Manager changes pushed to `main`.

## Real mod corpus

- [ ] Import and prepare at least one ZIP package and one extracted-folder mod.
- [x] Confirm the UM:PD Dark Mode self-installing EXE is rejected by the generic asset importer and is not executed.
- [ ] Import and prepare a standard hash-addressed ZIP such as Master Chocolate Cake or Doro Hat.
- [ ] Import and automatically prepare a deeply nested loose legacy GameBanana package such as Cafe Cat Keyhole Bra.
- [ ] Apply two non-conflicting mods and verify exact vanilla restoration.
- [ ] Apply two mods replacing the same hash and verify the load-order winner.
- [ ] Switch between at least three profiles without stale targets.
- [ ] Update one remotely sourced mod and verify version coexistence and rollback.
- [ ] Confirm an enabled unprepared mod blocks apply with a clear explanation.
- [ ] Change an active file outside UMML Manager and confirm normal deployment refuses to overwrite it.
- [ ] Corrupt a copy of `active.json` and confirm deployment fails before changing a game file.
- [ ] Exercise explicit force recovery and record the expected ownership result.

## Platforms, HTTPS, previews, controls, and game updates

- [x] Add unit coverage for Fedora/Bazzite CA-bundle fallback and explicit certificate environment variables.
- [x] Bundle `certifi/cacert.pem` and verify its presence in both package formats.
- [ ] Browse and download a current GameBanana mod from the packaged AppImage on Bazzite without certificate environment variables.
- [x] Confirm diagnostics reports the Bazzite system trust store or bundled certifi fallback.
- [ ] Verify selected-mod previews on Bazzite/KDE, including JPEG/PNG/WebP rendering.
- [ ] Rapidly switch selections and confirm a slow old preview cannot replace the current mod.
- [ ] Confirm missing or malformed previews remain nonfatal and do not disable Install/Open page.
- [ ] Verify Library controls with no selection, enabled/disabled mods, first/middle/last load order, prepared/stale/unprepared state, blockers, and game-running state.
- [ ] Verify Discover controls across first/last page, a changed query, incomplete file metadata, confirmed no-file submissions, local scan with and without a selected candidate, and a background import.
- [ ] Verify all legacy Studio cards show **Close game first** while Umamusume runs and reopen after it closes.
- [ ] Verify direct Settings entry edits clear verified target identity after Save, while Auto-detect preserves its new identity.
- [ ] Verify all shared-state operation buttons disable during a background task and restore afterward.
- [ ] Force game process detection to fail and confirm the badge reports unknown status while Apply and Studio writes remain blocked.
- [ ] Repeat GameBanana browse/download from the Debian package on a Debian/Ubuntu-family system.
- [ ] Test game-running detection on native Windows.
- [ ] Test game-running detection under Proton.
- [ ] Test after the game replaces `meta` and `dat` during an update.
- [ ] Verify prepared caches are invalidated or rebuilt when metadata changes.
- [ ] Verify a game update cannot silently replace the stored vanilla baseline.
- [ ] Test a game installation and Proton prefix on different Steam libraries.
- [ ] Test a machine with both Global and Japan installed and add an explicit installation chooser if automatic preference is ambiguous.

## Providers and archives

- [ ] Verify current GameBanana API response fields, file ordering, redirects, filenames, and preview hosts against multiple live submissions.
- [ ] Confirm switching pages/queries cannot install the previously selected submission.
- [x] Retain explicit file pinning, source metadata, archive SHA-256, size, and fetch time.
- [ ] Add safely inspected 7z/RAR support before advertising broad one-click compatibility for those formats.
- [x] Add extracted-file count and uncompressed-size limits before importing untrusted large archives.
- [ ] Confirm failed downloads and extraction leave no importable partial record on a real filesystem.
- [ ] Verify third-party license and attribution metadata remain visible.
- [ ] Add native Hachimi-runtime deployment or clearly keep pure Hachimi packages non-deployable and unprepared.

## Profiles and compatibility

- [x] Enforce declared Global/Japan/Taiwan region compatibility during profile planning.
- [x] Parse and enforce declared dependency and incompatibility IDs during planning.
- [ ] Add dependency discovery/install UX before advertising automatic dependency handling.
- [ ] Add profile duplicate, rename, and delete actions.
- [ ] Add a visible update action and version-switch workflow in the GUI.
- [ ] Verify older immutable versions remain discoverable and selectable after an update.

## Separate Debian package

- [x] CI builds `umml-manager_<MANAGER_VERSION>_amd64.deb` successfully.
- [x] Package metadata reports `Package: umml-manager` and the expected version.
- [ ] Install beside `umml-linux` and confirm there are no owned-file conflicts.
- [ ] Launch GUI from the desktop menu without a terminal.
- [ ] Confirm the Debian desktop entry starts `/usr/bin/umml-manager`, not a user PATH shadow.
- [ ] Test migration from the historical alpha1 `~/.local/bin` and per-user desktop entry.
- [ ] Run `umml-manager-cli --version` and an isolated-root `list` command from the installed package.
- [ ] Confirm the package does not need system `pip` or legacy UMML.
- [ ] Remove `umml-manager` and confirm legacy UMML remains installed and usable.
- [ ] Confirm package removal does not delete user library, profiles, state, or backups.
- [x] Validate desktop and AppStream metadata.

## Separate AppImage

- [x] CI builds the exact expected portable filename.
- [x] Version and CLI smoke tests run without FUSE through extraction mode.
- [x] Complete frozen runtime matches the shared source bundle and Debian payload.
- [x] Bundled certifi CA data and Pillow imaging support are present.
- [ ] Launch the alpha14 graphical interface on Bazzite/KDE.
- [ ] Launch on a second supported distribution.
- [ ] Verify Library, Discover, Studio, Conflicts, Settings, and diagnostics.
- [ ] Confirm AppImage and DEB see the same XDG manager data.

## Source installer

- [ ] Install without legacy UMML using a supported Python/Tk environment.
- [ ] Install with legacy UMML and confirm its isolated Python is reused.
- [ ] Confirm source code lives in `~/.local/share/umml-manager-app` while user data remains in `~/.local/share/umml-manager`.
- [ ] Confirm source-specific desktop ID and launchers do not shadow the Debian package.
- [ ] Run the current source uninstaller and confirm it preserves library, profiles, settings, baseline, transactions, downloads, and workspaces.
- [ ] Migrate an historical mixed alpha1 source install without deleting user data.

## Release behavior

- [ ] Keep remote installation opt-in.
- [ ] Preserve previous versions for rollback.
- [ ] Never execute code from downloaded mods.
- [ ] Keep runtime/native plugins outside the desktop manager.
- [ ] Attach sanitized logs and state manifests for release-candidate smoke tests.
- [x] Generate and verify external SHA-256 checksums for both package artifacts.
- [x] Update `MANAGER_VERSION`, changelog, READMEs, AppStream metadata, and artifact names together for alpha14.

## Runtime boundary

- [ ] Do not bundle an injector or Unity hook in either manager package.
- [ ] Unknown game builds expose zero hot-reload features.
- [ ] Queue profile changes for restart rather than writing game files in-process.
- [ ] Keep any future native adapter independently disableable and version-gated.

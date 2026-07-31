# Alpha19 Community Test campaign matrix

This matrix tracks real-machine and real-package evidence for **Uma Mod Manager 0.2.0-alpha.19**. It is intentionally separate from automated CI. A package being assembled correctly does not prove that Windows Explorer, KDE, Steam, Proton, the current game build, or a third-party mod will behave correctly in a real installation.

## Exact candidate

```text
Commit:          14d3a3095edc797fb882840461d715eda4894d20
MANAGER_VERSION: 0.2.0~alpha19
Portable:        0.2.0-alpha.19
Tag when ready:  v0.2.0-alpha.19
```

### Candidate checksums

```text
57232fec38dccfca3b9cfa5edf99ded01a66eabbedb533d42aa54a69385ca7f4  umml-manager_0.2.0-alpha.19_win64.zip
2b73c9b863cca031f00265e0eb9bea2750f6568d00ad89f34a2722991e33c020  umml-manager_0.2.0~alpha19_amd64.deb
39899a9b4fdc46e8d898c3087f7e39307bcb04e9e01062aa1ae3045566d1a5a5  umml-manager_0.2.0-alpha.19_x86_64.AppImage
```

These are exact workflow artifacts, not a published GitHub prerelease yet. Publication remains blocked until the minimum real-machine launch gates pass.

## Automated evidence

- Legacy UMML compatibility checks: run `30605310272` — passed.
- Uma Mod Manager Windows checks: run `30605310286` — passed.
- Uma Mod Manager Linux checks: run `30605310269` — both jobs passed.
- 219 Manager regressions passed on Windows and Linux; the Linux-only symlink test is skipped on Windows.
- Source and packaged GUI pages rendered in Light and Dark modes.
- Native Windows portable, Debian, and AppImage packages built and exercised.
- Debian install/remove preservation passed.
- Source/frozen/DEB/AppImage runtime parity passed.
- Release, branding, source-structure, desktop, AppStream, support-bundle privacy, and finished-package documentation audits passed.

## Minimum publication gates

### Windows portable

- [ ] Launch `Uma Mod Manager.cmd` without a development Python installation.
- [ ] Existing alpha18 library, profiles, settings, baselines, journals, and workspaces appear unchanged.
- [ ] Auto-detection selects the intended installation and region.
- [ ] System, Light, and Dark themes work and survive restart.
- [ ] Manager data and workspaces open in Explorer.
- [ ] Settings creates a support bundle and the JSON is manually inspected.
- [ ] Testing guide and feedback-form buttons open correctly.
- [ ] Manager-owned dialogs open in focus.

### Linux package

At least one of these is required before prerelease publication; both remain required before broader promotion.

#### Debian / Mint

- [ ] Install or upgrade the exact `.deb`.
- [ ] Existing Manager data survives upgrade and removal.
- [ ] Desktop entry, folder actions, themes, diagnostics, and support bundle work.
- [ ] Reinstalling the previous package remains a viable application rollback.

#### Bazzite / KDE

- [ ] Launch the exact AppImage.
- [ ] Desktop integration, folder actions, themes, diagnostics, and support bundle work.
- [ ] AppImage and Debian package use the same intended XDG Manager data.
- [ ] Keeping the previous AppImage provides application rollback.

## Priority mod and creator tests

- [ ] Import a normal hash-addressed ZIP.
- [ ] Import an extracted-folder mod.
- [ ] Import a deeply nested loose legacy package.
- [ ] Re-test the previously failing multi-target source bundle.
- [ ] Confirm preparation is automatic and no manual Prepare/Re-prepare control appears.
- [ ] Confirm one preparation failure does not stop unrelated packages.
- [ ] Select different authored variants in two profiles.
- [ ] Verify conflict winners and blockers match the displayed plan.
- [ ] Apply, switch profiles, and restore exact vanilla bytes using expendable or independently backed-up data.
- [ ] Confirm external file changes block ordinary deployment.
- [ ] Create or inspect a package, edit compatibility/options without JSON, and import a new immutable version.
- [ ] Confirm imported source bytes remain unchanged.
- [ ] Import classic and Werseter Veteran roster JSON and confirm unrelated output classes are rejected.

## Reporting

Use the repository's **Testing feedback** issue form for pass, partial, or failed results. Include:

- exact package filename and SHA-256;
- operating system, package format, game region, and native/Proton/Wine/DMM layout;
- clean installation or exact upgrade path;
- numbered steps;
- expected and actual results;
- whether game or Manager data changed;
- a manually reviewed support bundle;
- links to relevant third-party mods rather than unauthorized copies.

Do not attach copyrighted game files, decrypted databases, private roster dumps, credentials, or third-party mods without redistribution permission.

## Promotion rule

Do not publish or promote a replacement binary under the same tag or checksum. Any code, packaging, workflow, or documentation change that affects the shipped payload creates a new exact candidate and invalidates the evidence above. Metadata-only updates to the campaign issue may reference this candidate without rebuilding it.

# UMML Manager

UMML Manager is the full desktop manager and editing workspace for **Umamusume Pretty Derby** mods. It is packaged separately from legacy UMML while preserving the original loader's editing tools through a guarded compatibility Studio.

> **Preview:** `0.2.0~alpha18`. The manager includes bounded imports, immutable versions, provider browsing, automatic preparation and source-bundle analysis, profile-scoped configurable mods, visual package targeting and compatibility editing, a read-only veteran-roster workspace, verified metadata provenance, fail-closed deployment, recovery journals, automatic installation detection, legacy-baseline migration, Studio compatibility, and native Linux/Windows packages. Real-game and destructive recovery testing remain required before a stable release.

## Install

### Debian package

```bash
sudo apt install ./umml-manager_0.2.0~alpha18_amd64.deb
/usr/bin/umml-manager
```

The package can coexist with `umml-linux`. It owns `/usr/lib/umml-manager`, `/usr/bin/umml-manager`, and `/usr/bin/umml-manager-cli` only.

### AppImage

```bash
chmod +x ./umml-manager_0.2.0-alpha18_x86_64.AppImage
./umml-manager_0.2.0-alpha18_x86_64.AppImage
```

The same file exposes the CLI:

```bash
./umml-manager_0.2.0-alpha18_x86_64.AppImage --version
./umml-manager_0.2.0-alpha18_x86_64.AppImage --cli list
./umml-manager_0.2.0-alpha18_x86_64.AppImage --cli browse --region global
```

Linux formats use:

```text
~/.local/share/umml-manager
```

Windows portable builds use `%LOCALAPPDATA%\UMML Manager` for new state while preserving a detected early-preview root.

CI builds Linux formats from one PyInstaller bundle, compares their runtime trees, and builds a separate native Windows portable runtime. Completed artifacts receive external checksums.

```bash
sha256sum -c SHA256SUMS
```

### Historical source-install cleanup

Early previews mixed application code with manager data. Do not use an old alpha1 `uninstall-manager.sh`, because it could delete that mixed directory.

Remove only stale alpha1 launchers while preserving the library and recovery state:

```bash
rm -f ~/.local/bin/umml-manager ~/.local/bin/umml-manager-cli
rm -f ~/.local/share/applications/io.github.evelynlimab.ummlmanager.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
hash -r
```

The current source installer stores the complete Manager and legacy Studio source runtime in `~/.local/share/umml-manager-app` and state in `~/.local/share/umml-manager`. It requires Tk and Pillow and reports when optional Studio dependencies are unavailable. Its source-specific launchers do not replace an installed Debian package.

## Interface

- **Library:** immutable versions, profiles, load order, automatic preparation, detected source-bundle changes, profile choices, package creation/editing, and deployment.
- **Discover:** Global/Japan GameBanana browsing and bounded local package discovery.
- **Studio:** the complete legacy editor and loader interface behind process guards, plus the read-only Veteran Roster workspace.
- **Veteran Roster:** imports externally produced UmaExtractor `data.json`, removes known account identifiers, stores immutable local snapshots, filters and inspects records, and exports scrubbed JSON or CSV. UmaExtractor remains an external credited tool because its repository does not declare a project-wide license.
- **Conflicts:** exact file winners and every deployment blocker, including package-declared relative load order.
- **Settings:** installation detection, target paths, metadata identity, appearance, diagnostics, manager data, and workspaces.

### Context-aware controls

Visible controls follow actual prerequisites instead of silently doing nothing:

- selection actions require a valid Library or local-discovery row;
- **Enable** changes to **Disable** for enabled mods;
- explicit **Move up** and **Move down** actions follow the selected mod's real position;
- **Configure profile** appears for packages declaring profile options;
- **Inspect & edit** creates a focused workspace editor without modifying the imported source;
- detected characters, dresses, content types, parts, and target ownership are presented as evidence-backed suggestions;
- compatible imports, stale metadata, and older prepared records are prepared and indexed automatically;
- there is no user-facing Prepare or Re-prepare maintenance step;
- package-creation and package-editing controls disable while another Manager task owns shared state;
- Veteran Roster can remain read-only while the game runs, but it never elevates the Manager or receives deployment privileges;
- **Apply profile** remains explicit and is disabled while the game is running or the plan has blockers.

See [docs/UMAEXTRACTOR_INTEGRATION.md](docs/UMAEXTRACTOR_INTEGRATION.md) for the external-tool, privacy, and attribution boundary.

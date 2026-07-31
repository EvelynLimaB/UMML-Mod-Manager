# UMML-Manager feature roadmap

UMML-Manager is now the repository's primary product: a cross-platform player mod manager and creator workspace, forked from UMML.

The roadmap is ordered by dependency and risk. The project does not gain maturity by attaching more exciting tools to an unproven deployment path, though software has repeatedly attempted this strategy with admirable confidence.

## Foundations already implemented

- Versioned critical state and fail-closed schema handling.
- Immutable imported source versions and editable workspace copies.
- Automatic preparation and source analysis.
- One creator-facing source bundle owning multiple final game targets.
- Profile-scoped single-choice and multi-choice package options.
- Character, dress, content-type, part, region, tag, dependency, incompatibility, and relative-order metadata.
- Deterministic resolver and complete blocker reporting.
- Target-bound active state, vanilla baselines, locks, journals, snapshots, and integrity records.
- Transactional Apply, profile switching, restoration, rollback, and external-change protection.
- Bounded ZIP/TAR and local-folder import validation.
- Global/Japan GameBanana browsing with exact file provenance and bounded previews.
- Installation discovery across supported Steam, Proton, Wine, Windows, and regional layouts.
- Persistent Light, Dark, and System themes.
- Native Windows portable, Debian, and AppImage build pipelines.
- Guarded compatibility Studio preserving original UMML features.
- Read-only veteran-data snapshots and credited external extractor adapters.

## Phase 1: alpha stabilization and responsive player UX

### Goal

Make the existing player workflow reliable and pleasant on real Windows, Mint/Debian, Bazzite, and common display sizes.

### Work

- Complete real-machine automatic-preparation tests for multi-target community mods.
- Remove every remaining hidden or obsolete manual preparation control.
- Redesign Library around clear selection, status, configuration, conflict, and Apply hierarchy.
- Improve font scaling, keyboard navigation, focus, resizing, scrollbars, disabled states, and smaller-screen layouts.
- Consolidate duplicate game-running messages and explain why Apply is blocked in one place.
- Add a first-run walkthrough and contextual empty states.
- Complete target selection when several viable installations exist.
- Add a visible Recovery page for interrupted transactions, stale metadata, baselines, and external changes.
- Produce redacted one-click diagnostic bundles.

### Acceptance

- A first-time player can install, import, configure, apply, switch, and restore without documentation or manual preparation.
- Every Manager-owned window opens in front and remains reachable.
- No supported window size leaves primary actions tiny, clipped, or detached from their selected object.
- Exact Windows, Debian, and AppImage artifacts pass real-machine upgrade and persistence gates.

## Phase 2: complete visual mod-development workbench

### Goal

Make creating and adapting ordinary mods possible without hand-writing manifests or manually moving hashed files.

### Work

- Finish **Inspect & edit** around source bundles, target ownership, confidence, and compatibility.
- Add richer character, dress, part, content-type, and variant editors.
- Add source-bundle grouping, optional-component generation, and overlap visualization.
- Add before/after source and target comparison.
- Add a package validation report suitable for creators and release pages.
- Add example packages and redistributable synthetic fixtures.
- Add package export with README, changelog, manifest, credits, and license templates.
- Add a disposable test sandbox that plans, applies, verifies, switches, and restores without touching the primary installation.
- Add version history and compare two immutable versions.

### Acceptance

- A creator can inspect an existing permitted package, add accurate metadata, create a variant, test it, and export a new version through guided controls.
- Ordinary character/dress/component configuration requires no JSON.
- Detection confidence and creator corrections are both preserved.
- Testing proves the imported original remains byte-for-byte unchanged.

## Phase 3: provider-neutral discovery, downloads, and updates

### Goal

Turn Discover into a durable provider and update center rather than a single browsing page.

### Work

- Make the GUI consume an explicit provider registry.
- Add cached catalogue pages and a clearly marked offline view.
- Add durable download states: queued, downloading, verified, imported, failed, and cancelled.
- Add retry/backoff for transient failures without retrying certificate failures.
- Preserve every remote version and selected file.
- Add GitHub Releases and watched-folder providers.
- Add installed-versus-available comparison, changelogs, and update policies.
- Stage updates as new immutable versions.
- Let profiles select versions and roll back.

### Acceptance

- Provider failures never block local Library use.
- Every remote version links to exact provider, submission, file, version, hash, size, and fetch time.
- Updates never overwrite the previous working source or prepared cache.
- Profile version changes are visible in Conflicts before Apply.

## Phase 4: asset laboratory and external tools hub

### Goal

Give creators practical extraction, browsing, preview, and export workflows while preserving external projects' ownership and licenses.

### Work

- Add an External Tools page with project, author, version, platform, source, license, install/detect, and launch information.
- Add native asset indexing using verified game metadata and the existing UnityPy runtime.
- Add texture, sprite, text, metadata, and dependency previews.
- Add audio identification, playback, loop metadata, and export through a separately licensed backend.
- Add model, skeleton, material, and animation inventory.
- Add safe export workspaces and Blender bridge scripts.
- Add adapters for licensed tools such as AssetRipper, Blender, FFmpeg, vgmstream, and future Uma-specific viewers.
- Keep unlicensed projects external and user-supplied.
- Design a separate Godot-based 3D quick viewer rather than forcing rendering into Tk.

### Acceptance

- Asset tools are read-only toward the game installation.
- Exports carry source and tool provenance.
- External executables cannot access deployment state merely because they were launched from the Manager.
- Bundled tools have compatible licenses and complete notices.

## Phase 5: native Studio and generated mods

### Goal

Replace legacy popup editors incrementally while producing normal manageable packages.

### Work

- Extract character, dress, personality, training, concert, model-swap, translation, cleanup, and database logic into headless services.
- Represent asset changes as generated package workspaces.
- Represent database changes as fingerprinted patches with affected tables and original rows.
- Add preview, diff, validation, save-as-new-version, and export.
- Add operation-level game-running checks inside every service.
- Keep compatibility Studio until each parity row has tests and restoration coverage.

### Acceptance

- Native output can be enabled, ordered, conflicted, versioned, switched, and restored like any other mod.
- Database schema changes mark patches as needing rebase rather than replaying stale SQL.
- No working legacy feature disappears before its native replacement is demonstrably better.

## Phase 6: advanced Uma data workspaces

### Goal

Use credited external `umadump` and extractor output to provide useful local planning tools without bundling unlicensed scanners or modifying account data.

### Work

- Resolve character, card, skill, factor, race, support, and scenario IDs through the selected local `master.mdb`.
- Add decoded factor and lineage views.
- Add parent filters, comparison, compatibility, and goal-based ranking.
- Add support-card and owned-character collection views for Werseter output.
- Add friend/rental, trophy, race replay, and current-training workspaces.
- Track immutable snapshots and meaningful changes between them.
- Flag borrowed, transient, duplicate, or uncertain records visibly.

### Acceptance

- Personal identifiers are scrubbed before storage.
- Uncertain memory-derived records are never presented as confirmed ownership.
- Data tools remain read-only and separate from deployment privileges.
- Probability and ranking tools document their formulas, inputs, and assumptions.

## Phase 7: deployment backends and optional runtime bridge

### Goal

Support additional mod systems and explicitly allowlisted runtime capabilities without turning ordinary packages into native-code installers.

### Work

- Formalize prepare, plan, apply, restore, verify, and health-check backend interfaces.
- Keep the current hashed-asset backend as the reference implementation.
- Add linked-directory or Hachimi backends only after exact-version and real-machine testing.
- Model backend-owned paths and runtime requirements in the profile plan.
- Prevent two backends from claiming the same target without an explicit policy.
- Keep the runtime bridge separately packaged and disableable.
- Require exact game-build fingerprints and fail closed for unknown builds.
- Queue profile changes for restart unless a feature is proven hot-reload-safe.

### Acceptance

- Detection alone never enables an unsupported backend.
- Removing one backend cannot break another backend's restoration.
- Unknown builds expose zero runtime mutation capabilities.
- The desktop Manager remains fully usable without the runtime bridge.

## Phase 8: beta and stable release discipline

- Release channels for alpha, beta, and stable.
- Signed or otherwise verifiable release metadata where practical.
- Automatic update notifications with checksum verification and rollback-safe replacement.
- Migration notes and disposable upgrade tests for every stored-state change.
- Windows installer in addition to portable ZIP.
- Distribution packaging where maintainers can preserve the exact runtime contract.
- Localization-ready UI strings and contributor translation workflow.
- Accessibility review and documented keyboard operation.
- Storage quotas and safe pruning for downloads, previews, old versions, caches, and transactions.

## Permanent project rules

1. UMML-Manager is the primary product; legacy code is a compatibility layer, not the destination for new features.
2. No user-facing manual preparation or re-preparation workflow returns.
3. Imported source versions are immutable; edits and updates create new versions.
4. Detection is not deployment support and inference is not fact.
5. Downloads, manifests, external outputs, and archives remain untrusted input.
6. No game-file mutation occurs without a closed-game check, target identity, complete plan, recovery evidence, and verification.
7. Unknown state, builds, schemas, package types, and backends fail closed.
8. External projects retain attribution and require compatible licensing before bundling or modification.
9. Creator workflows should produce manageable packages with provenance and compatibility metadata.
10. Windows and Linux behavior must be tested independently.
11. Package builds must exercise their finished artifacts, not only source code.
12. The measure of success is more safe players and more maintainable mods, not merely more code.

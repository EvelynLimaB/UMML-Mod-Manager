# Blue Star Manager comparison pass

This review compares UMML Manager with Blue Star Manager's public CrossWorlds codebase. The goal is to adopt useful product patterns without copying its source or weakening UMML's immutable-library and transactional-deployment boundaries.

## Adopted in this pass

### Profile-scoped configurable packages

Blue Star demonstrates the value of a creator-declared configuration schema. UMML now supports native `option_groups` in `umml-mod.json` with single-choice and multiple-choice groups.

UMML's implementation deliberately differs:

- imported source versions remain immutable;
- choices use source asset path patterns rather than renaming files to a disabled suffix;
- preparation records source-path-to-target-hash mappings once;
- the profile stores each mod's selections;
- the resolver filters prepared claims before conflict planning;
- invalid, ambiguous, or stale configuration is a deployment blocker;
- uncontrolled files remain shared and enabled.

### Creator workspace entry point

Library now exposes **New package**, which creates a timestamped editable workspace with a valid `umml-mod.json`, `assets/`, metadata fields, and an optional two-choice configuration template. It does not silently import, enable, prepare, or apply the draft.

### Explicit configuration UI

Configurable Library records expose **Configure**. The modal editor uses radio buttons for single-choice groups and checkboxes for multiple-choice groups, validates selections, and stores them only in the active profile.

### Stronger structural coverage

The static UI callback audit now includes the package-builder and mod-options dialogs. The new option and package-builder cores are subject to the same architecture restrictions as other non-UI Manager layers.

## Already stronger in UMML

The comparison confirmed that these existing boundaries should remain:

- bounded extraction before immutable import;
- no archive replacement inside an existing source version;
- exact provider submission/file/hash provenance;
- deterministic resolver and visible blocker plan;
- prepared-cache metadata fingerprints;
- closed-game and process-inspection enforcement;
- target-bound vanilla baselines;
- staged atomic deployment, durable journal, rollback, and external-change protection;
- quarantining corrupt preferences instead of deleting evidence;
- shared backend behavior for GUI and CLI.

## Useful Blue Star ideas still planned

### Provider-neutral update center

Expose available provider files and versions in one Library view. Updating should import a new immutable version, compare manifests and conflicts, and let profiles switch deliberately. It must never overwrite the current source directory or executable.

### One-click URL handling

A future `umml:` desktop protocol can accept exact provider submission/file references and forward them to an existing Manager instance. The Manager must still show file metadata, archive trust information, and an import confirmation.

### Library organization

Add cosmetic sections/tags separately from profile membership and load order. Moving a visual section must never alter conflict precedence.

### Rich package builder

Expand the new-package workspace into a full manifest editor for dependencies, incompatibilities, regions, option groups, choice path previews, validation, and export.

### Version history

Show every immutable imported version, current profile selection, prepared status, and rollback action. This belongs above the existing library/resolver model, not inside provider download code.

## Patterns intentionally rejected

- deleting an existing mod folder before replacement extraction succeeds;
- mutable source folders controlled by renaming files;
- one overwrite-only backup directory without target identity or hashes;
- deleting malformed settings instead of preserving them;
- self-updates without a verified checksum or signed release metadata;
- mixing UI, provider, archive, backup, and deployment logic into one form class;
- treating a spawned desktop helper as proof that an external action succeeded;
- copying implementation code from a repository with no clear license grant.

## Acceptance rules for future borrowed ideas

1. Product convenience must use the public library, resolver, and deployment boundaries.
2. Remote or local inputs remain untrusted after download.
3. Updates create versions; they do not replace historical bytes.
4. Profile options must be deterministic and visible in the plan.
5. UI grouping must not invent load-order semantics.
6. Package tools create editable workspaces, never mutate immutable imports.
7. Finished DEB and AppImage runtimes must exercise every added page or dialog.

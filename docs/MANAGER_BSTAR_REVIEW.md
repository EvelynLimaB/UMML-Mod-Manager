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

### Semantic character and package targeting

Option groups may declare semantic kinds such as character, dress, colour, audio, quality, variant, or feature. Choices may carry target labels, and packages may describe affected characters, dresses, content types, and tags.

This remains honest about what metadata can do. A character selector chooses among character-specific assets already authored inside the package. Merely naming a different character does not rewrite arbitrary Unity bundle internals. That transformation belongs to a separately tested generated-mod backend.

### Creator workspace and manifest editor

Library exposes **New package**, which creates a timestamped editable workspace with a valid `umml-mod.json`, `assets/`, metadata fields, and optional generic or character-selectable templates. It does not silently import, enable, prepare, or apply the draft.

**Edit package** creates a workspace copy of an imported version and opens a native editor covering:

- identity and version;
- affected characters and dresses;
- content types and tags;
- regions;
- dependencies and incompatibilities;
- relative load-before/load-after rules;
- compatibility notes;
- advanced option-group JSON.

Saving edits only the workspace. Save-and-import still passes through validation and creates a normal immutable version.

### Explicit configuration UI

Configurable Library records expose **Configure**. The modal editor uses radio buttons for single-choice groups and checkboxes for multiple-choice groups, labels semantic targets, validates selections, and stores them only in the active profile.

### Stronger structural coverage

The static UI callback audit now includes package-builder, mod-options, and manifest-editor dialogs. The manifest, option, and package-builder cores are subject to the same architecture restrictions as other non-UI Manager layers.

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

Add cosmetic sections separately from profile membership and load order. Tags now exist as package metadata, but moving a visual section must never alter conflict precedence.

### Visual path and compatibility previews

The native editor validates policy and exposes advanced option JSON. A later preview should display which real source paths each choice controls, what targets they prepare into, and how a proposed compatibility change affects every profile before import.

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
7. Finished packages must exercise every added page or dialog on each advertised operating system.

# Creating mods with UMML-Manager

This guide describes the intended creator workflow in **UMML-Manager**. The current alpha already supports workspaces, source inspection, package metadata, compatibility rules, profile options, validation, immutable re-import, conflict planning, and transactional testing. Asset extraction, conversion, and richer previews are still growing.

The goal is to let creators spend more time changing the game and less time teaching strangers which hexadecimal folder to overwrite on a Tuesday.

## Before starting

Use only assets and tools you are legally allowed to use. Do not commit or publish:

- copyrighted game files;
- decrypted game databases;
- another mod author's work without permission;
- external tools whose license does not permit redistribution;
- account identifiers or personal roster data;
- executable installers disguised as ordinary mod packages.

Keep an untouched game installation or verified Manager baseline available for testing and restoration.

## Choose a starting point

### New package

Use **Library → New package** when starting from your own edited assets.

The Manager creates a timestamped workspace containing:

```text
umml-mod.json
assets/
PACKAGE_WORKSPACE.txt
```

The builder can start from:

- a blank package;
- a generic configurable variant template;
- a character-selectable variant template.

Creating a workspace does not import, enable, prepare, or deploy anything.

### Inspect an existing mod

Select an imported mod and use **Inspect & edit** when you want to:

- understand what its source bundles affect;
- add missing metadata;
- create a variant;
- correct compatibility information;
- split optional components;
- update it as a new version.

The Manager copies the imported source into a new editable workspace. The original imported version remains unchanged.

Do not use this workflow to republish another creator's work without permission. Technical ability and redistribution rights remain separate, because apparently society insisted on nuance.

## Workspace anatomy

A typical package looks like:

```text
my-mod/
├── umml-mod.json
├── assets/
│   ├── common/
│   ├── characters/
│   │   ├── special-week/
│   │   └── silence-suzuka/
│   └── optional/
│       ├── alternate-audio/
│       └── sparkles/
└── README.md
```

`assets/` contains creator-facing source files. During automatic preparation, UMML-Manager maps those sources to verified final game targets.

One authored source bundle may expand into several targets, such as:

```text
body.bundle
├── model target
├── material target
├── texture target
└── related metadata target
```

The Manager stores those targets together under the source bundle's isolated prepared payload. This prevents one variant from overwriting another during preparation.

## Identity metadata

Every package should define:

- a stable package ID;
- display name;
- author or team;
- version;
- description;
- supported regions;
- tags;
- source or homepage when appropriate;
- redistribution/license information when known.

Use a reverse-domain or creator-prefixed ID:

```text
creatorname.special-week-pink-costume
```

Do not change the ID for a normal update. Change the version.

A changed package ID represents a separate mod family. A changed version represents another immutable version of the same package.

## Describe what the mod affects

The guided editor supports affected:

- characters;
- dresses or costumes;
- content types;
- parts;
- regions;
- searchable tags.

Content types may include:

- model;
- texture;
- material;
- audio;
- animation;
- effects;
- UI;
- translation;
- database patch;
- other creator-defined categories.

Parts may include:

- body;
- face;
- hair;
- tail;
- ears;
- eyes;
- accessories;
- costume;
- voice;
- effects.

Detected suggestions are evidence, not authority. Review them before publishing.

### Descriptive targeting versus real variants

This metadata:

```json
{
  "targets": {
    "characters": ["Special Week"]
  }
}
```

says the package was authored for Special Week. It does not rewrite an arbitrary bundle to another character.

A real selectable character package must contain separately authored assets for each choice:

```text
assets/characters/special-week/
assets/characters/silence-suzuka/
```

The option group then decides which source set participates in the active profile.

## Add package options

Options belong to profiles. Two profiles may choose different variants from one immutable package.

### Single-choice groups

Use a single-choice group for mutually exclusive variants:

- character;
- dress;
- colour;
- quality level;
- alternate model;
- one of several audio sets.

Example concept:

```text
Character
◉ Special Week
○ Silence Suzuka
○ Tokai Teio
```

### Multiple-choice groups

Use a multiple-choice group for independent optional components:

```text
Extras
☑ Sparkles
☑ Alternate audio
☐ High-resolution textures
```

Do not place two choices in a multiple-choice group when their prepared sources claim the same final target. Overlapping choices need a single-choice group or an explicit conflict policy.

### Source include patterns

Choices select creator-facing sources, not final game hashes. For example:

```json
{
  "option_groups": {
    "character": {
      "kind": "character",
      "type": "single",
      "default": "special-week",
      "choices": {
        "special-week": {
          "label": "Special Week",
          "target": "1001",
          "include": ["characters/special-week/**"]
        },
        "silence-suzuka": {
          "label": "Silence Suzuka",
          "target": "1002",
          "include": ["characters/silence-suzuka/**"]
        }
      }
    }
  }
}
```

Patterns are validated. They may not:

- be absolute;
- contain parent traversal;
- match no prepared source;
- ambiguously assign one source to multiple choices in the same group;
- assign the same source to multiple option groups without a supported design.

See [MANAGER_MOD_MANIFEST.md](MANAGER_MOD_MANIFEST.md) for the complete schema.

## Compatibility metadata

Use the visual editor to define:

- required packages;
- incompatible packages;
- packages that must load before this one;
- packages that must load after this one;
- supported regions;
- compatibility notes.

Example:

```json
{
  "dependencies": ["creator.shared-base"],
  "incompatibilities": ["creator.old-body-model"],
  "load_after": ["creator.shared-base"],
  "regions": ["global"]
}
```

Dependencies and incompatibilities should use stable package IDs, not display names.

Relative order matters only when both packages are enabled. Ordinary file conflicts still follow profile load order, with later entries winning.

## Inspect source analysis

After import or workspace validation, the Manager analyzes source bundles automatically.

The inspection view may show:

- source path;
- source SHA-256;
- every final target owned by that source;
- likely content types;
- likely parts;
- character or dress IDs found in source names or metadata;
- overlapping targets;
- candidate optional components;
- candidate mutually exclusive variants.

Treat low-confidence suggestions as prompts for human review. Do not publish unsupported character claims merely because a number appeared somewhere in a filename.

## Validate and import

Use **Save manifest** to update only the editable workspace.

Use **Save and import** when the workspace is ready. UMML-Manager validates before adding a new immutable version.

Validation covers:

- manifest shape and required identity;
- safe package ID and version;
- path containment;
- source existence;
- option-group consistency;
- dependency and incompatibility contradictions;
- region policy;
- unsupported executable content;
- archive and local-folder limits;
- preparation requirements.

Invalid packages should fail before immutable source copying or registry changes.

## Test safely

Create a dedicated test profile.

Recommended sequence:

1. Enable only the package and its dependencies.
2. Select each profile option combination you intend to support.
3. Review Conflicts.
4. Confirm the intended final targets are owned by the expected source bundles.
5. Close the game.
6. Apply the test profile.
7. Launch the game and verify the intended content.
8. Close the game again.
9. Switch to another variant or profile.
10. Apply and verify.
11. Apply an empty profile or restore vanilla.
12. Run diagnostics and confirm no external-change or baseline warning remains.

For packages with overlapping character or component variants, test at least two variants that resolve to the same final target. This is the case most likely to expose incorrect source isolation.

## Publish a package

A distributable package should include:

- `umml-mod.json`;
- the required source assets;
- a human-readable README;
- author and contributor credits;
- version and changelog;
- supported regions and tested game builds;
- affected characters, dresses, and parts;
- dependencies and incompatibilities;
- known issues;
- install instructions pointing to UMML-Manager rather than manual hash copying;
- license or redistribution terms.

Do not include:

- Manager state;
- prepared caches;
- profiles;
- vanilla baselines;
- recovery journals;
- the game metadata database;
- unrelated external tools;
- copied game originals.

## Updating a mod

For an update:

1. Create or reopen an editable workspace.
2. Preserve the package ID.
3. Increase the version.
4. Make the changes.
5. review source analysis and compatibility again;
6. import as a new immutable version;
7. test profile switching and restoration;
8. publish the new archive without deleting the previous working release.

UMML-Manager's future update center will let profiles select versions and roll back. Keeping stable IDs and honest versions now makes that possible later.

## Useful contribution targets

Creators can improve the ecosystem even without writing Manager code:

- document common source-folder layouts;
- contribute synthetic packages reproducing preparation failures;
- record character/dress/part naming patterns without including game assets;
- add manifests to existing mods with permission;
- document dependencies and conflicts;
- write creator tutorials;
- request adapters for licensed external tools;
- report where the guided UI still forces ordinary users into JSON.

The project vision is in [PROJECT_VISION.md](PROJECT_VISION.md). Contributions are covered by [../CONTRIBUTING.md](../CONTRIBUTING.md).

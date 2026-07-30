# UMML Manager mod manifest

UMML Manager reads creator metadata from `umml-mod.json` in the package root. Legacy asset packages also contain an `assets/` directory.

Imported versions are immutable. Editing an imported package never changes that source record. **Edit package** creates a workspace copy; change its version or ID and import the edited workspace as a new immutable version.

## Basic metadata

```json
{
  "id": "creator.costume-pack",
  "title": "Costume Pack",
  "author": "Creator",
  "description": "A configurable costume package.",
  "mod_version": "1.0.0",
  "regions": ["global"],
  "tags": ["costume", "pink"],
  "targets": {
    "characters": ["1001", "Special Week"],
    "dresses": ["100101"],
    "content": ["model", "textures"]
  },
  "dependencies": ["creator.shared-base"],
  "incompatibilities": ["creator.old-costume-pack"],
  "load_after": ["creator.shared-base"],
  "load_before": [],
  "compatibility_notes": "Authored for the current Global model layout."
}
```

`targets` describes what the package was authored to affect. Target categories are extensible lowercase IDs. The Manager provides first-class UI fields for characters, dresses or costumes, and content types, while preserving other valid categories.

Target metadata is searchable and visible in Library, but it does **not** rewrite arbitrary Unity bundles. Declaring `"characters": ["Special Week"]` cannot turn a bundle authored for another character into a Special Week bundle. Actual retargeting would require a separate generated-transform backend with exact metadata and game-build validation.

## Compatibility policy

- `regions` accepts `global`, `japan`, `taiwan`, or `korea` and common aliases.
- `dependencies` lists mod IDs that must also be enabled.
- `incompatibilities` lists mod IDs that may not be enabled together.
- `load_after` and `load_before` describe relative order when both referenced mods are enabled.
- `compatibility_notes` is visible creator guidance, not an automatic override.

Dependencies, incompatibilities, region mismatches, and violated relative-order constraints are deployment blockers. The policy rejects self-references, one mod being both required and incompatible, or the same reference appearing in both `load_after` and `load_before`.

## Profile-scoped options

```json
{
  "id": "creator.costume-pack",
  "title": "Costume Pack",
  "mod_version": "1.0.0",
  "option_groups": {
    "character": {
      "name": "Affected character",
      "description": "Choose one authored character variant for this profile.",
      "kind": "character",
      "type": "single",
      "default": "special-week",
      "choices": {
        "special-week": {
          "name": "Special Week",
          "target": "1001",
          "include": ["characters/special-week/**"]
        },
        "silence-suzuka": {
          "name": "Silence Suzuka",
          "target": "1002",
          "include": ["characters/silence-suzuka/**"]
        }
      }
    },
    "color": {
      "name": "Costume colour",
      "kind": "color",
      "type": "single",
      "default": "pink",
      "choices": {
        "pink": {
          "name": "Pink",
          "include": ["variants/pink/**"]
        },
        "blue": {
          "name": "Blue",
          "include": ["variants/blue/**"]
        }
      }
    },
    "extras": {
      "name": "Optional extras",
      "kind": "feature",
      "type": "multiple",
      "default": ["sparkles"],
      "choices": {
        "sparkles": {
          "name": "Sparkle effects",
          "include": ["extras/sparkles/**"]
        },
        "alternate-audio": {
          "name": "Alternate audio",
          "include": ["extras/audio/**"]
        }
      }
    }
  }
}
```

`single` groups select exactly one choice. `multiple` groups select zero or more choices; use `required: true` when at least one choice is mandatory.

`kind` is a semantic UI label. Built-in labels include `character`, `dress`, `color`, `audio`, `quality`, `variant`, and `feature`; custom identifier-safe kinds remain valid. A choice's optional `target` gives a human-readable or game-facing ID for display and documentation.

Selections are saved in the active profile. Preparation records the mapping from source asset paths to final target hashes. Resolution then includes only the prepared files selected by the profile. Files not matched by any option choice remain enabled as shared content.

A character option therefore selects between **already authored character-specific asset sets** such as `assets/characters/special-week/**` and `assets/characters/silence-suzuka/**`. It does not mutate files, rename them to `.disabled`, or patch character IDs inside arbitrary bundles.

## Native editor workflow

1. Use **Library → New package** or select an imported mod and choose **Edit package**.
2. Fill identity, affected characters or dresses, content types, tags, regions, dependencies, incompatibilities, relative order, and notes.
3. Generate a character selector when the workspace contains separately authored character variants.
4. Use the Options tab for custom groups or advanced path patterns.
5. Save the workspace, then use **Save and import** to create a normal immutable library version.
6. Prepare the version, select its profile options, inspect Conflicts, and apply only after all blockers are cleared.

## Validation rules

Configuration and compatibility fail closed when:

- IDs contain unsupported characters;
- include paths are absolute or contain `..`;
- a pattern matches no prepared asset;
- one source file matches multiple choices or groups;
- a profile selects an unknown group or choice;
- a prepared cache predates source-to-target mapping support;
- a region is unsupported;
- dependency, incompatibility, or relative-order IDs are malformed;
- compatibility declarations contradict each other;
- a required option has no selected choice.

Older configurable packages need one **Re-prepare** after import. This does not modify their immutable source.

UMML Manager deliberately avoids changing option state by renaming files inside the imported package. Every selection still passes through the normal resolver, conflict plan, process guard, transaction, baseline, verification, and rollback boundaries.

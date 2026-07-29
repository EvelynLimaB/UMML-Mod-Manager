# UMML Manager mod manifest

UMML Manager reads creator metadata from `umml-mod.json` in the package root. Legacy asset packages also contain an `assets/` directory.

Imported versions are immutable. Editing the original folder does not change an imported record; update the version and import it again.

## Basic metadata

```json
{
  "id": "creator.costume-pack",
  "title": "Costume Pack",
  "author": "Creator",
  "description": "A configurable costume package.",
  "mod_version": "1.0.0",
  "regions": ["global"],
  "dependencies": ["creator.shared-base"],
  "incompatibilities": ["creator.old-costume-pack"]
}
```

## Profile-scoped options

```json
{
  "id": "creator.costume-pack",
  "title": "Costume Pack",
  "mod_version": "1.0.0",
  "option_groups": {
    "color": {
      "name": "Costume color",
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

Selections are saved in the active profile. Preparation records the mapping from source asset paths to final target hashes. Resolution then includes only the prepared files selected by the profile. Files not matched by any option choice remain enabled as shared content.

## Validation rules

Configuration fails closed when:

- IDs contain unsupported characters;
- include paths are absolute or contain `..`;
- a pattern matches no prepared asset;
- one source file matches multiple choices or groups;
- a profile selects an unknown group or choice;
- a prepared cache predates source-to-target mapping support.

Older configurable packages need one **Re-prepare** after import. This does not modify their immutable source.

UMML Manager deliberately avoids changing option state by renaming files inside the imported package. Every selection still passes through the normal resolver, conflict plan, process guard, transaction, baseline, verification, and rollback boundaries.

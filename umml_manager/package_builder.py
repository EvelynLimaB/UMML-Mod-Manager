from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .manifest import normalize_manifest_policy
from .options import normalize_option_groups
from .safety import atomic_write_json, validate_regular_tree
from .store import ManagerStore, StoreError, sanitize_id


@dataclass(frozen=True)
class PackageDraft:
    mod_id: str
    title: str
    version: str
    author: str = ""
    description: str = ""
    regions: tuple[str, ...] = ()
    target_characters: tuple[str, ...] = ()
    target_dresses: tuple[str, ...] = ()
    content_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    incompatibilities: tuple[str, ...] = ()
    load_after: tuple[str, ...] = ()
    load_before: tuple[str, ...] = ()
    compatibility_notes: str = ""
    configurable_template: bool = False
    character_template: bool = False


def create_package_workspace(store: ManagerStore, draft: PackageDraft) -> Path:
    """Create a new editable package workspace without importing it."""

    mod_id = sanitize_id(draft.mod_id)
    if mod_id != draft.mod_id.strip().casefold():
        raise StoreError(
            "Package ID must be lowercase and use letters, digits, dots, underscores, or hyphens."
        )
    title = draft.title.strip()
    version = draft.version.strip()
    if not title:
        raise StoreError("Package title cannot be empty")
    if not version:
        raise StoreError("Package version cannot be empty")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination = store.paths.workspaces / "new-packages" / mod_id / stamp
    if destination.exists():
        raise StoreError(f"Package workspace already exists: {destination}")

    assets = destination / "assets"
    assets.mkdir(parents=True)
    targets: dict[str, list[str]] = {}
    if draft.target_characters:
        targets["characters"] = list(draft.target_characters)
    if draft.target_dresses:
        targets["dresses"] = list(draft.target_dresses)
    if draft.content_types:
        targets["content"] = list(draft.content_types)

    manifest: dict[str, object] = {
        "id": mod_id,
        "title": title,
        "author": draft.author.strip(),
        "description": draft.description.strip(),
        "mod_version": version,
        "regions": [value for value in draft.regions if value],
        "targets": targets,
        "tags": [value for value in draft.tags if value],
        "dependencies": [value for value in draft.dependencies if value],
        "incompatibilities": [value for value in draft.incompatibilities if value],
        "load_after": [value for value in draft.load_after if value],
        "load_before": [value for value in draft.load_before if value],
        "compatibility_notes": draft.compatibility_notes.strip(),
    }

    groups: dict[str, object] = {}
    instructions: list[str] = [
        "Put package files under assets. Increase mod_version before importing a changed version."
    ]
    if draft.configurable_template:
        groups["variant"] = {
            "name": "Variant",
            "description": "Choose one package variant for this profile.",
            "kind": "variant",
            "type": "single",
            "default": "first",
            "choices": {
                "first": {
                    "name": "First variant",
                    "include": ["variants/first/**"],
                },
                "second": {
                    "name": "Second variant",
                    "include": ["variants/second/**"],
                },
            },
        }
        (assets / "variants" / "first").mkdir(parents=True)
        (assets / "variants" / "second").mkdir(parents=True)
        (assets / "common").mkdir(parents=True, exist_ok=True)
        instructions.append(
            "Put shared files in assets/common and choice-specific files in assets/variants/<choice>."
        )

    if draft.character_template:
        characters = list(draft.target_characters) or ["Character one", "Character two"]
        choices: dict[str, object] = {}
        used: set[str] = set()
        for character in characters:
            choice_id = _choice_id(character, used)
            used.add(choice_id)
            choices[choice_id] = {
                "name": character,
                "target": character,
                "include": [f"characters/{choice_id}/**"],
            }
            (assets / "characters" / choice_id).mkdir(parents=True, exist_ok=True)
        groups["character"] = {
            "name": "Affected character",
            "description": (
                "Select which authored character-specific asset set this profile deploys. "
                "This selects packaged variants; it does not rewrite arbitrary bundles."
            ),
            "kind": "character",
            "type": "single",
            "default": next(iter(choices)),
            "choices": choices,
        }
        (assets / "common").mkdir(parents=True, exist_ok=True)
        instructions.append(
            "Put each authored character variant under assets/characters/<choice>. "
            "The profile selector includes one variant without modifying source files."
        )

    if groups:
        manifest["option_groups"] = normalize_option_groups(groups)

    try:
        policy = normalize_manifest_policy(manifest, mod_id=mod_id)
    except ValueError as exc:
        raise StoreError(f"Invalid package draft: {exc}") from exc
    manifest.update(
        {
            "regions": policy.regions,
            "targets": policy.targets,
            "tags": policy.tags,
            "dependencies": policy.dependencies,
            "incompatibilities": policy.incompatibilities,
            "load_after": policy.load_after,
            "load_before": policy.load_before,
            "compatibility_notes": policy.compatibility_notes,
            "option_groups": policy.option_groups,
        }
    )

    atomic_write_json(destination / "umml-mod.json", manifest)
    (destination / "PACKAGE_WORKSPACE.txt").write_text(
        "\n".join(instructions) + "\n",
        encoding="utf-8",
    )
    validate_regular_tree(destination)
    return destination


def _choice_id(value: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9._-]+", "-", value.casefold()).strip("-.")
    base = base[:48] or "character"
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate

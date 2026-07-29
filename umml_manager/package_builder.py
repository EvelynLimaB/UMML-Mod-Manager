from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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
    configurable_template: bool = False


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
    manifest: dict[str, object] = {
        "id": mod_id,
        "title": title,
        "author": draft.author.strip(),
        "description": draft.description.strip(),
        "mod_version": version,
        "regions": [value for value in draft.regions if value],
        "dependencies": [],
        "incompatibilities": [],
    }

    if draft.configurable_template:
        groups = {
            "variant": {
                "name": "Variant",
                "description": "Choose one package variant for this profile.",
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
        }
        manifest["option_groups"] = normalize_option_groups(groups)
        (assets / "variants" / "first").mkdir(parents=True)
        (assets / "variants" / "second").mkdir(parents=True)
        (assets / "common").mkdir(parents=True)
        instructions = (
            "Put shared files in assets/common and choice-specific files in the variant folders. "
            "Edit umml-mod.json to rename or add choices.\n"
        )
    else:
        instructions = (
            "Put package files under assets. Increase mod_version before importing a changed version.\n"
        )

    atomic_write_json(destination / "umml-mod.json", manifest)
    (destination / "PACKAGE_WORKSPACE.txt").write_text(instructions, encoding="utf-8")
    validate_regular_tree(destination)
    return destination

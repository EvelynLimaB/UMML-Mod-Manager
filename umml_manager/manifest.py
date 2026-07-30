from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .options import normalize_option_groups
from .regions import SUPPORTED_REGIONS, normalize_region

_MOD_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
_TARGET_CATEGORY = re.compile(r"^[a-z][a-z0-9._-]{0,31}$")
_MAX_LIST_ITEMS = 256
_MAX_VALUE_LENGTH = 256


class ManifestError(ValueError):
    """Raised when creator-facing package policy is malformed."""


@dataclass(frozen=True)
class ManifestPolicy:
    option_groups: dict[str, dict[str, Any]]
    targets: dict[str, list[str]]
    tags: list[str]
    regions: list[str]
    dependencies: list[str]
    incompatibilities: list[str]
    load_after: list[str]
    load_before: list[str]
    compatibility_notes: str


def normalize_manifest_policy(
    metadata: Mapping[str, Any],
    *,
    mod_id: str = "",
) -> ManifestPolicy:
    """Validate package targeting, options, and compatibility as one policy.

    Target metadata describes what a package was authored to affect. It never
    rewrites arbitrary Unity bundles. Actual per-profile character or dress
    selection is represented by an option group whose choices include the
    corresponding prepared source paths.
    """

    if not isinstance(metadata, Mapping):
        raise ManifestError("mod manifest must be an object")

    regions = _regions(metadata.get("regions", metadata.get("region", [])))
    dependencies = _mod_references(metadata.get("dependencies", []), "dependencies")
    incompatibilities = _mod_references(
        metadata.get("incompatibilities", []),
        "incompatibilities",
    )
    load_after = _mod_references(metadata.get("load_after", []), "load_after")
    load_before = _mod_references(metadata.get("load_before", []), "load_before")

    canonical_id = str(mod_id or metadata.get("id") or "").strip().casefold()
    if canonical_id:
        for label, values in (
            ("dependencies", dependencies),
            ("incompatibilities", incompatibilities),
            ("load_after", load_after),
            ("load_before", load_before),
        ):
            if canonical_id in values:
                raise ManifestError(f"{label} cannot reference the package itself: {canonical_id}")

    contradictory = sorted(set(dependencies) & set(incompatibilities))
    if contradictory:
        raise ManifestError(
            "the same mod cannot be both required and incompatible: "
            + ", ".join(contradictory)
        )
    contradictory_order = sorted(set(load_after) & set(load_before))
    if contradictory_order:
        raise ManifestError(
            "the same mod cannot be required both before and after this package: "
            + ", ".join(contradictory_order)
        )

    targets_value = metadata.get("targets", {})
    if targets_value in (None, ""):
        targets_value = {}
    if not isinstance(targets_value, Mapping):
        raise ManifestError("targets must be an object")
    targets_input = dict(targets_value)
    aliases = {
        "characters": metadata.get("affected_characters", metadata.get("characters")),
        "dresses": metadata.get("affected_dresses", metadata.get("dresses")),
        "content": metadata.get("content_types", metadata.get("content")),
    }
    for key, value in aliases.items():
        if key not in targets_input and value not in (None, "", [], ()):
            targets_input[key] = value

    notes = str(metadata.get("compatibility_notes") or "").strip()
    if len(notes) > 4000:
        raise ManifestError("compatibility_notes is limited to 4000 characters")

    return ManifestPolicy(
        option_groups=normalize_option_groups(metadata.get("option_groups", {})),
        targets=normalize_targets(targets_input),
        tags=_display_values(metadata.get("tags", []), "tags", casefold=True),
        regions=regions,
        dependencies=dependencies,
        incompatibilities=incompatibilities,
        load_after=load_after,
        load_before=load_before,
        compatibility_notes=notes,
    )


def normalize_targets(value: object) -> dict[str, list[str]]:
    if value in (None, ""):
        return {}
    if not isinstance(value, Mapping):
        raise ManifestError("targets must be an object")
    result: dict[str, list[str]] = {}
    for raw_key, raw_values in value.items():
        key = str(raw_key).strip().casefold()
        if not _TARGET_CATEGORY.fullmatch(key):
            raise ManifestError(
                f"target category {key!r} must use lowercase letters, digits, dots, underscores, or hyphens"
            )
        values = _display_values(raw_values, f"targets.{key}")
        if values:
            result[key] = values
    return result


def _regions(value: object) -> list[str]:
    result: list[str] = []
    for raw in _raw_values(value, "regions"):
        region = normalize_region(raw, default="")
        if region not in SUPPORTED_REGIONS:
            raise ManifestError(
                f"unsupported region {raw!r}; expected one of {', '.join(SUPPORTED_REGIONS)}"
            )
        if region not in result:
            result.append(region)
    return result


def _mod_references(value: object, label: str) -> list[str]:
    result: list[str] = []
    for raw in _raw_values(value, label):
        item = raw.casefold()
        if not _MOD_ID.fullmatch(item):
            raise ManifestError(
                f"{label} entry {raw!r} must be a stable lowercase mod ID"
            )
        if item not in result:
            result.append(item)
    return result


def _display_values(value: object, label: str, *, casefold: bool = False) -> list[str]:
    result: list[str] = []
    for raw in _raw_values(value, label):
        item = raw.casefold() if casefold else raw
        if item not in result:
            result.append(item)
    return result


def _raw_values(value: object, label: str) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raise ManifestError(f"{label} must be a string or list")
    if len(raw_values) > _MAX_LIST_ITEMS:
        raise ManifestError(f"{label} contains more than {_MAX_LIST_ITEMS} entries")
    result: list[str] = []
    for raw in raw_values:
        item = str(raw).strip()
        if not item:
            continue
        if len(item) > _MAX_VALUE_LENGTH:
            raise ManifestError(
                f"{label} entry is longer than {_MAX_VALUE_LENGTH} characters"
            )
        result.append(item)
    return result

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping

_OPTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SUPPORTED_TYPES = {"single", "multiple"}


class OptionError(ValueError):
    """Raised when a configurable-mod manifest or profile selection is invalid."""


def normalize_option_groups(value: object) -> dict[str, dict[str, Any]]:
    """Return a validated, JSON-safe configurable-mod manifest.

    The native UMML format deliberately keeps creator-facing source paths. A
    choice controls one or more files under ``assets/`` through POSIX glob
    patterns. Preparation records the source-to-target mapping; profile
    resolution then selects the appropriate prepared hashes without modifying
    the immutable source tree.

    ``kind`` and choice ``target`` are semantic labels. They let the interface
    present a group as a character, dress, colour, audio, quality, or custom
    selector without pretending that metadata alone can rewrite an arbitrary
    Unity bundle.
    """

    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise OptionError("option_groups must be an object")

    groups: dict[str, dict[str, Any]] = {}
    for raw_group_id, raw_group in value.items():
        group_id = _identifier(raw_group_id, "option group")
        if group_id in groups:
            raise OptionError(f"duplicate option group: {group_id}")
        if not isinstance(raw_group, dict):
            raise OptionError(f"option group {group_id!r} must be an object")

        option_type = str(raw_group.get("type", "single")).strip().casefold()
        aliases = {
            "selectone": "single",
            "select-one": "single",
            "selectmultiple": "multiple",
            "select-multiple": "multiple",
        }
        option_type = aliases.get(option_type, option_type)
        if option_type not in _SUPPORTED_TYPES:
            raise OptionError(
                f"option group {group_id!r} has unsupported type {option_type!r}"
            )
        kind = str(raw_group.get("kind") or "generic").strip().casefold()
        if not _OPTION_ID.fullmatch(kind):
            raise OptionError(
                f"option group {group_id!r} kind {kind!r} must use letters, digits, dots, underscores, or hyphens"
            )

        raw_choices = raw_group.get("choices", {})
        if not isinstance(raw_choices, dict) or not raw_choices:
            raise OptionError(f"option group {group_id!r} must define choices")

        choices: dict[str, dict[str, Any]] = {}
        for raw_choice_id, raw_choice in raw_choices.items():
            choice_id = _identifier(raw_choice_id, f"choice in {group_id}")
            if choice_id in choices:
                raise OptionError(
                    f"duplicate choice {choice_id!r} in option group {group_id!r}"
                )
            if isinstance(raw_choice, str):
                raw_choice = {"include": [raw_choice]}
            if not isinstance(raw_choice, dict):
                raise OptionError(
                    f"choice {group_id}.{choice_id} must be an object"
                )
            include = _patterns(
                raw_choice.get("include", []),
                label=f"choice {group_id}.{choice_id}",
            )
            if not include:
                raise OptionError(
                    f"choice {group_id}.{choice_id} must include at least one assets path"
                )
            target = str(raw_choice.get("target") or "").strip()
            if len(target) > 256:
                raise OptionError(
                    f"choice {group_id}.{choice_id} target is longer than 256 characters"
                )
            choices[choice_id] = {
                "name": str(raw_choice.get("name") or choice_id),
                "description": str(raw_choice.get("description") or ""),
                "target": target,
                "include": include,
            }

        default = _selection_values(raw_group.get("default", []))
        if not default and option_type == "single":
            default = [next(iter(choices))]
        required = bool(raw_group.get("required", option_type == "single"))
        _validate_group_selection(
            group_id,
            option_type,
            required,
            choices,
            default,
            source="default",
        )

        groups[group_id] = {
            "name": str(raw_group.get("name") or group_id),
            "description": str(raw_group.get("description") or ""),
            "kind": kind,
            "type": option_type,
            "required": required,
            "default": default,
            "choices": choices,
        }
    return groups


def normalize_profile_options(
    groups: Mapping[str, Mapping[str, Any]],
    value: object,
    *,
    reject_unknown: bool = True,
) -> dict[str, list[str]]:
    """Validate one profile's selections and fill omitted groups from defaults."""

    canonical_groups = normalize_option_groups(dict(groups))
    if value in (None, ""):
        raw: dict[str, Any] = {}
    elif isinstance(value, dict):
        raw = dict(value)
    else:
        raise OptionError("profile mod options must be an object")

    if reject_unknown:
        unknown = sorted(str(key) for key in raw if str(key) not in canonical_groups)
        if unknown:
            raise OptionError("unknown option group(s): " + ", ".join(unknown))

    selections: dict[str, list[str]] = {}
    for group_id, group in canonical_groups.items():
        selected = _selection_values(raw.get(group_id, group["default"]))
        _validate_group_selection(
            group_id,
            str(group["type"]),
            bool(group["required"]),
            dict(group["choices"]),
            selected,
            source="profile",
        )
        selections[group_id] = selected
    return selections


def select_source_paths(
    groups: Mapping[str, Mapping[str, Any]],
    selections: object,
    source_paths: Iterable[str],
) -> set[str]:
    """Return source assets enabled by a validated profile selection.

    Files not controlled by any choice stay enabled. A file may be controlled by
    exactly one choice in exactly one group. Ambiguous patterns fail closed
    instead of silently inventing precedence rules that creators never asked for.
    Every declared pattern must match at least one prepared source path.
    """

    canonical_groups = normalize_option_groups(dict(groups))
    selected = normalize_profile_options(canonical_groups, selections)
    paths = sorted({_source_path(path) for path in source_paths})

    pattern_hits: dict[tuple[str, str, str], int] = {}
    for group_id, group in canonical_groups.items():
        for choice_id, choice in dict(group["choices"]).items():
            for pattern in choice["include"]:
                pattern_hits[(group_id, choice_id, pattern)] = 0

    enabled: set[str] = set()
    for path in paths:
        matching_groups: dict[str, list[str]] = {}
        for group_id, group in canonical_groups.items():
            matched_choices: list[str] = []
            for choice_id, choice in dict(group["choices"]).items():
                if any(_matches(path, pattern) for pattern in choice["include"]):
                    matched_choices.append(choice_id)
                    for pattern in choice["include"]:
                        if _matches(path, pattern):
                            pattern_hits[(group_id, choice_id, pattern)] += 1
            if matched_choices:
                matching_groups[group_id] = matched_choices

        if not matching_groups:
            enabled.add(path)
            continue
        if len(matching_groups) > 1:
            owners = ", ".join(sorted(matching_groups))
            raise OptionError(
                f"assets path {path!r} is controlled by multiple option groups: {owners}"
            )

        group_id, matched_choices = next(iter(matching_groups.items()))
        if len(matched_choices) > 1:
            raise OptionError(
                f"assets path {path!r} matches multiple choices in {group_id!r}: "
                + ", ".join(sorted(matched_choices))
            )
        if matched_choices[0] in selected[group_id]:
            enabled.add(path)

    missing_patterns = [
        f"{group}.{choice}: {pattern}"
        for (group, choice, pattern), count in pattern_hits.items()
        if count == 0
    ]
    if missing_patterns:
        raise OptionError(
            "option include pattern(s) matched no prepared assets: "
            + "; ".join(missing_patterns)
        )
    return enabled


def option_summary(
    groups: Mapping[str, Mapping[str, Any]],
    selections: object,
) -> str:
    canonical_groups = normalize_option_groups(dict(groups))
    selected = normalize_profile_options(canonical_groups, selections)
    parts: list[str] = []
    for group_id, group in canonical_groups.items():
        choice_names = [
            str(group["choices"][choice_id]["name"])
            for choice_id in selected[group_id]
        ]
        value = ", ".join(choice_names) if choice_names else "None"
        parts.append(f"{group['name']}: {value}")
    return " • ".join(parts)


def option_signature(
    groups: Mapping[str, Mapping[str, Any]],
    selections: object,
) -> str:
    canonical = normalize_profile_options(groups, selections)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _identifier(value: object, label: str) -> str:
    text = str(value).strip()
    if not _OPTION_ID.fullmatch(text):
        raise OptionError(
            f"{label} ID {text!r} must use 1-64 letters, digits, dots, underscores, or hyphens"
        )
    return text


def _patterns(value: object, *, label: str) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        raise OptionError(f"{label} include must be a string or list")
    result: list[str] = []
    for raw in values:
        pattern = str(raw).strip().replace("\\", "/")
        if not pattern:
            continue
        pure = PurePosixPath(pattern)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise OptionError(f"unsafe assets include pattern: {pattern!r}")
        if pattern.startswith("assets/"):
            pattern = pattern[len("assets/") :]
        if pattern not in result:
            result.append(pattern)
    return result


def _source_path(value: object) -> str:
    text = str(value).strip().replace("\\", "/")
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise OptionError(f"unsafe source assets path: {text!r}")
    return pure.as_posix()


def _selection_values(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raise OptionError("option selection must be a string or list")
    result: list[str] = []
    for item in raw:
        choice_id = str(item).strip()
        if choice_id and choice_id not in result:
            result.append(choice_id)
    return result


def _validate_group_selection(
    group_id: str,
    option_type: str,
    required: bool,
    choices: Mapping[str, Any],
    selected: list[str],
    *,
    source: str,
) -> None:
    unknown = [choice for choice in selected if choice not in choices]
    if unknown:
        raise OptionError(
            f"{source} selection for {group_id!r} contains unknown choice(s): "
            + ", ".join(unknown)
        )
    if option_type == "single" and len(selected) != 1:
        raise OptionError(
            f"{source} selection for single-choice group {group_id!r} must contain exactly one choice"
        )
    if required and not selected:
        raise OptionError(f"{source} selection for required group {group_id!r} is empty")


def _matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern)

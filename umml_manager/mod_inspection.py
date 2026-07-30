from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import ModRecord


_CHARACTER_PATTERNS = (
    re.compile(r"(?:^|[/_.-])(?:chara|character|chr)[/_-]?(\d{3,8})(?:$|[/_.-])", re.I),
    re.compile(r"(?:^|[/_.-])(?:face|head|hair|tail|ear)[_-]?(\d{3,8})(?:$|[/_.-])", re.I),
)
_DRESS_PATTERNS = (
    re.compile(r"(?:^|[/_.-])(?:dress|costume|outfit|cloth)[/_-]?(\d{4,10})(?:$|[/_.-])", re.I),
    re.compile(r"(?:^|[/_.-])bdy[_-]?(\d{5,10})(?:$|[/_.-])", re.I),
)
_OPAQUE_PATH = re.compile(r"^(?:[0-9a-f]{2}/)?[0-9a-f]{32,64}$", re.I)


@dataclass(frozen=True)
class AssetFinding:
    source: str
    target: str
    label: str
    content_type: str
    part: str
    character_ids: tuple[str, ...] = ()
    dress_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModInspection:
    findings: tuple[AssetFinding, ...]
    content_types: tuple[str, ...]
    parts: tuple[str, ...]
    character_ids: tuple[str, ...]
    dress_ids: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def source_count(self) -> int:
        return len(self.findings)

    @property
    def target_count(self) -> int:
        return len({item.target for item in self.findings if item.target})

    def summary(self) -> str:
        if not self.findings:
            return "No inspectable asset mapping is available yet"
        pieces = [f"{self.source_count} asset(s) → {self.target_count} game target(s)"]
        if self.parts:
            pieces.append("parts: " + ", ".join(self.parts[:5]))
        if self.character_ids:
            pieces.append("character ID(s): " + ", ".join(self.character_ids))
        if self.dress_ids:
            pieces.append("dress ID(s): " + ", ".join(self.dress_ids))
        return " • ".join(pieces)


def inspect_mod(record: ModRecord) -> ModInspection:
    mappings = _source_mappings(record)
    findings = tuple(
        _finding(source, target)
        for source, target in sorted(mappings.items())
    )
    content_types = _ordered_unique(item.content_type for item in findings if item.content_type)
    parts = _ordered_unique(item.part for item in findings if item.part)
    character_ids = _ordered_unique(
        value for item in findings for value in item.character_ids
    )
    dress_ids = _ordered_unique(value for item in findings for value in item.dress_ids)

    warnings: list[str] = []
    if not findings:
        warnings.append(
            "Prepare the mod first so the Manager can map creator-facing assets to game targets."
        )
    elif all(_OPAQUE_PATH.fullmatch(item.source) for item in findings):
        warnings.append(
            "The package exposes only opaque hashes, so character and part detection is limited."
        )
    if findings and not character_ids:
        warnings.append(
            "No reliable character ID was present in the asset names. The title is only a hint, not proof."
        )
    return ModInspection(
        findings=findings,
        content_types=content_types,
        parts=parts,
        character_ids=character_ids,
        dress_ids=dress_ids,
        warnings=tuple(warnings),
    )


def build_component_option_groups(
    inspection: ModInspection,
    *,
    preserve: dict[str, dict] | None = None,
) -> dict[str, dict]:
    """Create safe profile controls from exact source-to-target ownership.

    One-source targets become independently toggleable components. Multiple sources
    that resolve to the same target become mutually exclusive variant selectors.
    """

    groups = dict(preserve or {})
    by_target: dict[str, list[AssetFinding]] = {}
    for finding in inspection.findings:
        if not finding.target:
            continue
        by_target.setdefault(finding.target, []).append(finding)

    optional = [items[0] for items in by_target.values() if len(items) == 1]
    if optional:
        choices: dict[str, dict] = {}
        defaults: list[str] = []
        used: set[str] = set()
        for index, finding in enumerate(optional, start=1):
            choice_id = _unique_id(_slug(finding.label) or f"component-{index}", used)
            defaults.append(choice_id)
            choices[choice_id] = {
                "name": finding.label,
                "description": _choice_description(finding),
                "include": [finding.source],
            }
        groups["components"] = {
            "name": "Included components",
            "description": "Enable or disable individual detected files for this profile.",
            "kind": "feature",
            "type": "multiple",
            "default": defaults,
            "choices": choices,
        }

    variant_number = 0
    for target, items in sorted(by_target.items()):
        if len(items) < 2:
            continue
        variant_number += 1
        used: set[str] = set()
        choices: dict[str, dict] = {}
        for index, finding in enumerate(items, start=1):
            choice_id = _unique_id(_slug(finding.label) or f"variant-{index}", used)
            choices[choice_id] = {
                "name": finding.label,
                "description": _choice_description(finding),
                "include": [finding.source],
            }
        group_id = f"detected-variant-{variant_number}"
        groups[group_id] = {
            "name": f"Variant for {Path(target).name[:12]}",
            "description": "These authored files replace the same game target and cannot be active together.",
            "kind": "variant",
            "type": "single",
            "default": next(iter(choices)),
            "choices": choices,
        }
    return groups


def _source_mappings(record: ModRecord) -> dict[str, str]:
    if record.source_files:
        return {
            str(source).replace("\\", "/").strip("/"): str(target).replace("\\", "/").strip("/")
            for source, target in record.source_files.items()
            if str(source).strip()
        }

    assets = Path(record.source_path).expanduser() / "assets"
    if assets.is_dir():
        files = [item for item in assets.rglob("*") if item.is_file()]
        if files:
            targets = list(record.files)
            result: dict[str, str] = {}
            for item in files:
                relative = item.relative_to(assets).as_posix()
                matches = [target for target in targets if Path(target).name == item.name]
                result[relative] = matches[0] if len(matches) == 1 else ""
            return result

    return {str(target): str(target) for target in record.files}


def _finding(source: str, target: str) -> AssetFinding:
    normalized = source.replace("\\", "/").strip("/")
    lowered = normalized.casefold()
    tokens = set(filter(None, re.split(r"[/_.\-\s]+", lowered)))
    content_type = _content_type(lowered, tokens)
    part = _part(lowered, tokens, content_type)
    characters = _matches(_CHARACTER_PATTERNS, lowered)
    dresses = _matches(_DRESS_PATTERNS, lowered)
    label = _human_label(normalized, part, content_type)
    return AssetFinding(
        source=normalized,
        target=target,
        label=label,
        content_type=content_type,
        part=part,
        character_ids=characters,
        dress_ids=dresses,
    )


def _content_type(path: str, tokens: set[str]) -> str:
    suffix = Path(path).suffix.casefold()
    if suffix in {".acb", ".awb"} or tokens & {"audio", "sound", "voice", "bgm", "se"}:
        return "audio"
    if suffix == ".usm" or tokens & {"movie", "video", "cutscene"}:
        return "video"
    if tokens & {"anim", "animation", "motion", "anm"}:
        return "animation"
    if tokens & {"effect", "effects", "fx", "vfx", "particle"}:
        return "effects"
    if tokens & {"texture", "textures", "tex", "atlas", "sprite", "icon"}:
        return "textures"
    if tokens & {"ui", "interface", "button", "banner"}:
        return "ui"
    if tokens & {
        "model",
        "mesh",
        "prefab",
        "pfb",
        "body",
        "bdy",
        "head",
        "face",
        "hair",
        "tail",
        "ear",
        "cloth",
        "dress",
        "costume",
        "outfit",
        "accessory",
        "acc",
    }:
        return "model"
    return "asset"


def _part(path: str, tokens: set[str], content_type: str) -> str:
    checks = (
        ("glasses", {"glasses", "glass", "eyewear", "spectacles"}),
        ("accessory", {"accessory", "accessories", "acc", "ornament"}),
        ("face", {"face", "eye", "eyes", "mouth", "brow", "eyebrow"}),
        ("hair", {"hair", "bang", "fringe"}),
        ("head", {"head", "hat", "cap", "crown"}),
        ("ears", {"ear", "ears"}),
        ("tail", {"tail"}),
        ("body", {"body", "bdy", "torso", "skin"}),
        ("dress / costume", {"dress", "costume", "outfit", "cloth", "clothes"}),
        ("animation", {"anim", "animation", "motion", "anm"}),
        ("audio", {"audio", "sound", "voice", "bgm", "se"}),
        ("effects", {"effect", "effects", "fx", "vfx", "particle"}),
        ("UI", {"ui", "interface", "button", "banner", "icon"}),
    )
    for label, markers in checks:
        if tokens & markers:
            return label
    if "glass" in path:
        return "glasses"
    return content_type


def _human_label(source: str, part: str, content_type: str) -> str:
    name = Path(source).name
    if _OPAQUE_PATH.fullmatch(source):
        return f"{part.title()} file {name[:12]}"
    cleaned = re.sub(r"[_\-.]+", " ", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned or cleaned.casefold() in {"body", "asset", "file"}:
        cleaned = Path(source).parent.name.replace("_", " ").replace("-", " ")
    label = cleaned.title() if cleaned else part.title()
    if part and part.casefold() not in label.casefold() and content_type != "asset":
        label += f" · {part}"
    return label


def _matches(patterns: Iterable[re.Pattern[str]], value: str) -> tuple[str, ...]:
    found: list[str] = []
    for pattern in patterns:
        found.extend(match.group(1) for match in pattern.finditer(value))
    return _ordered_unique(found)


def _choice_description(finding: AssetFinding) -> str:
    details = [finding.part or finding.content_type]
    if finding.character_ids:
        details.append("character " + ", ".join(finding.character_ids))
    if finding.dress_ids:
        details.append("dress " + ", ".join(finding.dress_ids))
    details.append("target " + (Path(finding.target).name[:12] if finding.target else "unknown"))
    return " • ".join(item for item in details if item)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value).strip()))


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return result[:48]


def _unique_id(candidate: str, used: set[str]) -> str:
    base = candidate or "choice"
    current = base
    number = 2
    while current in used:
        current = f"{base}-{number}"
        number += 1
    used.add(current)
    return current

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class RosterEntry:
    """Readable factor or skill extracted from a roster record."""

    id: str
    name: str
    level: int
    level_known: bool

    @property
    def level_label(self) -> str:
        if not self.level_known:
            return "—"
        return f"{self.level}★" if self.level > 0 else "—"


@dataclass(frozen=True)
class FactorQuality:
    count: int
    known_levels: int
    total_stars: int
    three_star_count: int

    @property
    def summary(self) -> str:
        if not self.count:
            return "No factors"
        if not self.known_levels:
            return f"{self.count} factor(s) · levels unavailable"
        return (
            f"{self.count} factor(s) · {self.total_stars} known stars · "
            f"{self.three_star_count} at 3★"
        )


_FACTOR_KEYS = (
    "factor_info_array",
    "factor_id_array",
    "factorDataArray",
    "factors",
    "factor_array",
)
_SKILL_KEYS = (
    "skill_array",
    "acquiredSkillArray",
    "skills",
    "skill_id_array",
)
_FACTOR_LEVELS = frozenset((1, 2, 3))


def factor_entries(record: dict[str, Any]) -> tuple[RosterEntry, ...]:
    return _entries(
        _first(record, *_FACTOR_KEYS),
        id_keys=("factor_id", "factorId", "id"),
        name_keys=("factor_name", "factorName", "name", "label"),
        level_keys=("level", "factor_level", "factorLevel", "star"),
        fallback_level_keys=("rarity",),
        valid_levels=_FACTOR_LEVELS,
        fallback_prefix="Factor",
    )


def skill_entries(record: dict[str, Any]) -> tuple[RosterEntry, ...]:
    return _entries(
        _first(record, *_SKILL_KEYS),
        id_keys=("skill_id", "skillId", "id"),
        name_keys=("skill_name", "skillName", "name", "label"),
        level_keys=("level", "skill_level", "skillLevel", "rarity"),
        fallback_prefix="Skill",
    )


def factor_quality(record: dict[str, Any]) -> FactorQuality:
    entries = factor_entries(record)
    known = [entry.level for entry in entries if entry.level_known]
    return FactorQuality(
        count=len(entries),
        known_levels=len(known),
        total_stars=sum(known),
        three_star_count=sum(level >= 3 for level in known),
    )


def aptitude_entries(record: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for key, value in record.items():
        if not _normalized_key(str(key)).startswith("proper"):
            continue
        if value in (None, "", 0):
            continue
        label = _humanize_key(str(key)).removeprefix("proper ")
        values.append((label.title(), str(value)))
    values.sort(key=lambda item: item[0].casefold())
    return tuple(values)


def legacy_sort_key(record: dict[str, Any], total_stats: int) -> tuple[int, int, int, int]:
    """Rank likely legacy candidates without pretending to know compatibility.

    Known three-star factors are strongest, then known star total, factor count,
    and finally total stats as a stable tie-breaker.
    """

    quality = factor_quality(record)
    return (
        quality.three_star_count,
        quality.total_stars,
        quality.count,
        int(total_stats),
    )


def shared_entry_ids(
    left: Iterable[RosterEntry],
    right: Iterable[RosterEntry],
) -> tuple[str, ...]:
    left_ids = {entry.id for entry in left if entry.id}
    right_ids = {entry.id for entry in right if entry.id}
    return tuple(sorted(left_ids.intersection(right_ids), key=_natural_key))


def comparison_rows(left_row: Any, right_row: Any) -> tuple[tuple[str, int, int, int], ...]:
    rows: list[tuple[str, int, int, int]] = []
    for label, attribute in (
        ("Speed", "speed"),
        ("Stamina", "stamina"),
        ("Power", "power"),
        ("Guts", "guts"),
        ("Wisdom", "wisdom"),
        ("Total stats", "total_stats"),
        ("Factors", "factor_count"),
        ("Skills", "skill_count"),
    ):
        left_value = int(getattr(left_row, attribute, 0))
        right_value = int(getattr(right_row, attribute, 0))
        rows.append((label, left_value, right_value - left_value, right_value))
    return tuple(rows)


def _entries(
    raw: Any,
    *,
    id_keys: tuple[str, ...],
    name_keys: tuple[str, ...],
    level_keys: tuple[str, ...],
    fallback_prefix: str,
    fallback_level_keys: tuple[str, ...] = (),
    valid_levels: frozenset[int] | None = None,
) -> tuple[RosterEntry, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()

    values: list[RosterEntry] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            identifier = _text(_first(item, *id_keys))
            explicit_name = _text(_first(item, *name_keys))
            raw_level = _first(item, *level_keys)
            level_known, level = _resolved_level(raw_level, valid_levels)
            if not level_known and fallback_level_keys:
                level_known, level = _resolved_level(
                    _first(item, *fallback_level_keys),
                    valid_levels,
                )
        else:
            identifier = _text(item)
            explicit_name = ""
            level_known = False
            level = 0

        if not identifier:
            identifier = str(index + 1)
        name = explicit_name or f"{fallback_prefix} {identifier}"
        values.append(
            RosterEntry(
                id=identifier,
                name=name,
                level=max(0, level),
                level_known=level_known,
            )
        )
    return tuple(values)


def _resolved_level(
    raw_level: Any,
    valid_levels: frozenset[int] | None,
) -> tuple[bool, int]:
    if raw_level in (None, ""):
        return False, 0
    level = _integer(raw_level)
    if valid_levels is not None and level not in valid_levels:
        return False, 0
    return True, level


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalized_key(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _humanize_key(value: str) -> str:
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"(?<!^)(?=[A-Z])", " ", value)
    return " ".join(value.casefold().split())


def _natural_key(value: str) -> tuple[Any, ...]:
    return tuple(
        int(part) if part.isdigit() else part.casefold()
        for part in re.split(r"(\d+)", value)
    )

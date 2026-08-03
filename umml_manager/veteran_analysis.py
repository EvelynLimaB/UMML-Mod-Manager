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
    level_kind: str = "stars"

    @property
    def level_label(self) -> str:
        if not self.level_known or self.level <= 0:
            return "—"
        if self.level_kind == "level":
            return f"Lv {self.level}"
        return f"{self.level}★"


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
_APTITUDE_GRADES = {
    1: "G",
    2: "F",
    3: "E",
    4: "D",
    5: "C",
    6: "B",
    7: "A",
    8: "S",
}
_RANK_PATTERN = re.compile(r"^(?:[A-G](?:\+)?|SS\+?|U[GFEDCBAS](?:[1-9])?|US7\+)$", re.I)

# Evaluation-point thresholds used by the game. Keep this descending so the
# first matching threshold is the visible rank. The current published table
# defines US through US7; values above it are labelled US7+ instead of
# inventing unpublished US8/US9 boundaries.
_EVALUATION_RANKS: tuple[tuple[int, str], ...] = (
    (71_600, "US7"),
    (70_300, "US6"),
    (69_000, "US5"),
    (67_700, "US4"),
    (66_400, "US3"),
    (65_100, "US2"),
    (64_200, "US1"),
    (63_400, "US"),
    (62_500, "UA9"),
    (61_700, "UA8"),
    (60_800, "UA7"),
    (60_000, "UA6"),
    (59_200, "UA5"),
    (58_400, "UA4"),
    (57_500, "UA3"),
    (56_700, "UA2"),
    (55_900, "UA1"),
    (55_200, "UA"),
    (54_400, "UB9"),
    (53_600, "UB8"),
    (52_800, "UB7"),
    (52_000, "UB6"),
    (51_300, "UB5"),
    (50_500, "UB4"),
    (49_800, "UB3"),
    (49_000, "UB2"),
    (48_300, "UB1"),
    (47_600, "UB"),
    (46_900, "UC9"),
    (46_200, "UC8"),
    (45_400, "UC7"),
    (44_700, "UC6"),
    (44_000, "UC5"),
    (43_400, "UC4"),
    (42_700, "UC3"),
    (42_000, "UC2"),
    (41_300, "UC1"),
    (40_700, "UC"),
    (40_000, "UD9"),
    (39_400, "UD8"),
    (38_700, "UD7"),
    (38_100, "UD6"),
    (37_500, "UD5"),
    (36_800, "UD4"),
    (36_200, "UD3"),
    (35_600, "UD2"),
    (35_000, "UD1"),
    (34_400, "UD"),
    (33_800, "UE9"),
    (33_200, "UE8"),
    (32_700, "UE7"),
    (32_100, "UE6"),
    (31_500, "UE5"),
    (31_000, "UE4"),
    (30_400, "UE3"),
    (29_900, "UE2"),
    (29_400, "UE1"),
    (28_800, "UE"),
    (28_300, "UF9"),
    (27_800, "UF8"),
    (27_300, "UF7"),
    (26_800, "UF6"),
    (26_300, "UF5"),
    (25_800, "UF4"),
    (25_300, "UF3"),
    (24_800, "UF2"),
    (24_300, "UF1"),
    (23_900, "UF"),
    (23_400, "UG9"),
    (23_000, "UG8"),
    (22_500, "UG7"),
    (22_100, "UG6"),
    (21_600, "UG5"),
    (21_200, "UG4"),
    (20_800, "UG3"),
    (20_400, "UG2"),
    (20_000, "UG1"),
    (19_600, "UG"),
    (19_200, "SS+"),
    (17_500, "SS"),
    (15_900, "S+"),
    (14_500, "S"),
    (12_100, "A+"),
    (10_000, "A"),
    (8_200, "B+"),
    (6_500, "B"),
    (4_900, "C+"),
    (3_500, "C"),
    (2_900, "D+"),
    (2_300, "D"),
    (1_800, "E+"),
    (1_300, "E"),
    (900, "F+"),
    (600, "F"),
    (300, "G+"),
    (0, "G"),
)


def factor_entries(record: dict[str, Any]) -> tuple[RosterEntry, ...]:
    return _entries(
        _first(record, *_FACTOR_KEYS),
        id_keys=("factor_id", "factorId", "id"),
        name_keys=("factor_name", "factorName", "name", "label"),
        level_keys=("level", "factor_level", "factorLevel", "star"),
        fallback_level_keys=("rarity",),
        valid_levels=_FACTOR_LEVELS,
        fallback_prefix="Factor",
        level_kind="stars",
    )


def skill_entries(record: dict[str, Any]) -> tuple[RosterEntry, ...]:
    # Master-data rarity describes the skill itself; it is not the acquired
    # skill level from the trained-character record. Keep those concepts apart.
    return _entries(
        _first(record, *_SKILL_KEYS),
        id_keys=("skill_id", "skillId", "id"),
        name_keys=("skill_name", "skillName", "name", "label"),
        level_keys=("level", "skill_level", "skillLevel"),
        fallback_prefix="Skill",
        minimum_level=1,
        level_kind="level",
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


def aptitude_grade(value: Any) -> str:
    """Return the game's G-through-S aptitude label for extractor values."""

    text = _text(value).upper().replace(" ", "")
    if text in set(_APTITUDE_GRADES.values()):
        return text
    numeric = _integer_or_none(value)
    if numeric is None or numeric <= 0:
        return "—"
    return _APTITUDE_GRADES.get(numeric, text)


def aptitude_entries(record: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for key, value in record.items():
        if not _normalized_key(str(key)).startswith("proper"):
            continue
        if value in (None, "", 0):
            continue
        label = _humanize_key(str(key)).removeprefix("proper ")
        values.append((label.title(), aptitude_grade(value)))
    values.sort(key=lambda item: item[0].casefold())
    return tuple(values)


def evaluation_score(record: dict[str, Any]) -> int | None:
    """Return a numeric evaluation point without treating rank labels as scores."""

    for key in (
        "evaluation_point",
        "evaluationPoint",
        "rank_score",
        "rankScore",
        "evaluation",
        "rank",
    ):
        if key not in record:
            continue
        score = _integer_or_none(record.get(key))
        if score is not None and score >= 0:
            return score
    return None


def evaluation_rank(value: Any) -> str:
    """Convert an evaluation score or already-readable label to a game rank."""

    text = _text(value).upper().replace(" ", "")
    if text and _RANK_PATTERN.fullmatch(text):
        return text
    score = _integer_or_none(value)
    if score is None or score < 0:
        return "—"
    if score > _EVALUATION_RANKS[0][0]:
        return "US7+"
    for threshold, label in _EVALUATION_RANKS:
        if score >= threshold:
            return label
    return "G"


def evaluation_rank_from_record(record: dict[str, Any]) -> str:
    """Prefer an explicit rank label, otherwise derive it from evaluation points."""

    for key in ("rank_name", "rankName", "rank"):
        value = record.get(key)
        text = _text(value).upper().replace(" ", "")
        if text and _RANK_PATTERN.fullmatch(text):
            return text
    score = evaluation_score(record)
    return evaluation_rank(score) if score is not None else "—"


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
    minimum_level: int | None = None,
    level_kind: str = "stars",
) -> tuple[RosterEntry, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()

    values: list[RosterEntry] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            identifier = _text(_first(item, *id_keys))
            explicit_name = _text(_first(item, *name_keys))
            raw_level = _first(item, *level_keys)
            level_known, level = _resolved_level(
                raw_level,
                valid_levels,
                minimum_level=minimum_level,
            )
            if not level_known and fallback_level_keys:
                level_known, level = _resolved_level(
                    _first(item, *fallback_level_keys),
                    valid_levels,
                    minimum_level=minimum_level,
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
                level_kind=level_kind,
            )
        )
    return tuple(values)


def _resolved_level(
    raw_level: Any,
    valid_levels: frozenset[int] | None,
    *,
    minimum_level: int | None = None,
) -> tuple[bool, int]:
    if raw_level in (None, ""):
        return False, 0
    level = _integer(raw_level)
    if valid_levels is not None and level not in valid_levels:
        return False, 0
    if minimum_level is not None and level < minimum_level:
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


def _integer_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        text = str(value).strip()
        if not text or not re.fullmatch(r"[+-]?\d+", text):
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


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

from __future__ import annotations

import copy
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


CARD_NAME_CATEGORY = 4
COSTUME_NAME_CATEGORY = 5
CHARACTER_NAME_CATEGORY = 6
SKILL_NAME_CATEGORY = 47
SKILL_DESCRIPTION_CATEGORY = 48
FACTOR_AND_ALT_SKILL_NAME_CATEGORY = 147
FACTOR_DESCRIPTION_CATEGORY = 172

FACTOR_TYPE_LABELS = {
    1: "Blue stat",
    2: "Red aptitude",
    3: "Unique",
    4: "White skill",
    5: "White race",
    6: "Scenario",
    7: "Event",
}

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


class VeteranMasterDataError(RuntimeError):
    """Raised when a discovered master database cannot be read safely."""


@dataclass(frozen=True)
class VeteranMasterResolution:
    records: list[dict[str, Any]]
    master_path: Path | None
    card_records: int = 0
    factor_entries: int = 0
    skill_entries: int = 0
    unresolved_cards: int = 0
    unresolved_factors: int = 0
    unresolved_skills: int = 0
    warnings: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return self.master_path is not None

    @property
    def summary(self) -> str:
        if self.master_path is None:
            return (
                "Local master data was not found. Names and exact Spark levels fall back "
                "to fields included by the extractor."
            )
        resolved = (
            f"Master data: {self.card_records:,} veteran identity record(s), "
            f"{self.factor_entries:,} Spark entry/entries, and "
            f"{self.skill_entries:,} skill entry/entries resolved read-only."
        )
        missing = self.unresolved_cards + self.unresolved_factors + self.unresolved_skills
        if missing:
            resolved += (
                f" {missing:,} ID reference(s) were not present in this installed database."
            )
        if self.warnings:
            resolved += " " + " ".join(self.warnings)
        return resolved


def discover_master_mdb(app: Any) -> Path | None:
    """Find the current installation's master.mdb without scanning arbitrary disks."""

    candidates: list[Path] = []

    settings: dict[str, Any] = {}
    store = getattr(app, "store", None)
    if store is not None:
        try:
            loaded = store.load_settings()
            if isinstance(loaded, dict):
                settings = loaded
        except Exception:
            settings = {}

    explicit = _text(settings.get("master_path"))
    if explicit:
        candidates.append(Path(explicit).expanduser())

    for attribute in ("dat_path", "meta_path"):
        value = _app_value(app, attribute)
        if not value:
            continue
        path = Path(value).expanduser()
        persistent = path.parent if path.name.casefold() in {"dat", "meta"} else path
        candidates.append(persistent / "master" / "master.mdb")

    game_dir_value = _app_value(app, "game_dir")
    if game_dir_value:
        game_dir = Path(game_dir_value).expanduser()
        persistent_roots = (
            game_dir / "UmamusumePrettyDerby_Data" / "Persistent",
            game_dir / "Umamusume_Data" / "Persistent",
            game_dir / "Persistent",
            game_dir,
        )
        candidates.extend(root / "master" / "master.mdb" for root in persistent_roots)

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def resolve_veteran_records(
    records: Iterable[dict[str, Any]],
    master_path: str | Path | None,
) -> VeteranMasterResolution:
    """Enrich scrubbed roster records from the user's own current master.mdb.

    The database is opened with SQLite's read-only and immutable flags. The
    returned records are deep copies; snapshots on disk and the game database
    are never modified.
    """

    source_records = [copy.deepcopy(record) for record in records]
    if master_path is None:
        return VeteranMasterResolution(records=source_records, master_path=None)

    path = Path(master_path).expanduser()
    if not path.is_file():
        return VeteranMasterResolution(records=source_records, master_path=None)

    connection = _open_read_only(path)
    try:
        tables = _table_names(connection)
        if "text_data" not in tables:
            raise VeteranMasterDataError(
                "The installed master.mdb has no text_data table."
            )

        card_names = _text_map(connection, CARD_NAME_CATEGORY)
        costume_names = _text_map(connection, COSTUME_NAME_CATEGORY)
        character_names = _text_map(connection, CHARACTER_NAME_CATEGORY)
        skill_names = _text_map(connection, SKILL_NAME_CATEGORY)
        factor_and_alt_skill_names = _text_map(
            connection,
            FACTOR_AND_ALT_SKILL_NAME_CATEGORY,
        )
        skill_descriptions = _text_map(connection, SKILL_DESCRIPTION_CATEGORY)
        factor_descriptions = _text_map(connection, FACTOR_DESCRIPTION_CATEGORY)

        cards = _load_cards(
            connection,
            tables,
            card_names=card_names,
            costume_names=costume_names,
            character_names=character_names,
        )
        factors = _load_factors(
            connection,
            tables,
            names=factor_and_alt_skill_names,
            descriptions=factor_descriptions,
        )
        skills = _load_skills(
            connection,
            tables,
            names=skill_names,
            alternate_names=factor_and_alt_skill_names,
            descriptions=skill_descriptions,
        )

        counts = {
            "card_records": 0,
            "factor_entries": 0,
            "skill_entries": 0,
            "unresolved_cards": 0,
            "unresolved_factors": 0,
            "unresolved_skills": 0,
        }
        enriched = [
            _resolve_record(record, cards, factors, skills, counts)
            for record in source_records
        ]

        warnings: list[str] = []
        for table, label in (
            ("card_data", "card identities"),
            ("succession_factor", "Spark metadata"),
            ("skill_data", "skill metadata"),
        ):
            if table not in tables:
                warnings.append(f"The installed database has no {table} table; {label} are partial.")

        return VeteranMasterResolution(
            records=enriched,
            master_path=path.resolve(),
            warnings=tuple(warnings),
            **counts,
        )
    except VeteranMasterDataError:
        raise
    except sqlite3.Error as exc:
        raise VeteranMasterDataError(
            f"Could not query the installed master.mdb safely: {exc}"
        ) from exc
    finally:
        connection.close()


def _open_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    uri_path = quote(resolved.as_posix(), safe="/:")
    try:
        connection = sqlite3.connect(
            f"file:{uri_path}?mode=ro&immutable=1",
            uri=True,
            timeout=5,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        return connection
    except sqlite3.Error as exc:
        try:
            connection.close()
        except (UnboundLocalError, sqlite3.Error):
            pass
        raise VeteranMasterDataError(
            "The installed master.mdb could not be opened as a read-only SQLite "
            f"database: {exc}"
        ) from exc


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    safe_table = table.replace('"', '""')
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{safe_table}")')
    }


def _text_map(connection: sqlite3.Connection, category: int) -> dict[int, str]:
    result: dict[int, str] = {}
    try:
        rows = connection.execute(
            'SELECT "index", text FROM text_data WHERE category = ?',
            (category,),
        )
    except sqlite3.Error:
        return result
    for row in rows:
        identifier = _integer_or_none(row[0])
        text = _text(row[1])
        if identifier is not None and text:
            result[identifier] = text
    return result


def _load_cards(
    connection: sqlite3.Connection,
    tables: set[str],
    *,
    card_names: dict[int, str],
    costume_names: dict[int, str],
    character_names: dict[int, str],
) -> dict[int, dict[str, Any]]:
    if "card_data" not in tables:
        return {}
    columns = _table_columns(connection, "card_data")
    if not {"id", "chara_id"}.issubset(columns):
        return {}
    cards: dict[int, dict[str, Any]] = {}
    for row in connection.execute("SELECT id, chara_id FROM card_data"):
        card_id = _integer_or_none(row[0])
        chara_id = _integer_or_none(row[1])
        if card_id is None or chara_id is None:
            continue
        character_name = character_names.get(chara_id, "")
        costume_name = costume_names.get(card_id, "")
        card_name = card_names.get(card_id, "")
        if not card_name:
            card_name = " ".join(
                value for value in (costume_name, character_name) if value
            ).strip()
        cards[card_id] = {
            "card_id": card_id,
            "chara_id": chara_id,
            "chara_name": character_name,
            "costume_name": costume_name,
            "card_name": card_name,
        }
    return cards


def _load_factors(
    connection: sqlite3.Connection,
    tables: set[str],
    *,
    names: dict[int, str],
    descriptions: dict[int, str],
) -> dict[int, dict[str, Any]]:
    if "succession_factor" not in tables:
        return {}
    columns = _table_columns(connection, "succession_factor")
    if "factor_id" not in columns:
        return {}
    optional = [
        name
        for name in (
            "factor_group_id",
            "rarity",
            "factor_type",
            "effect_group_id",
            "target_type",
            "target_value",
        )
        if name in columns
    ]
    selection = ", ".join(["factor_id", *optional])
    factors: dict[int, dict[str, Any]] = {}
    for row in connection.execute(f"SELECT {selection} FROM succession_factor"):
        values = dict(row)
        factor_id = _integer_or_none(values.get("factor_id"))
        if factor_id is None:
            continue
        factor_type = _integer_or_none(values.get("factor_type"))
        info: dict[str, Any] = {
            "factor_id": factor_id,
            "factor_name": names.get(factor_id, ""),
            "factor_description": descriptions.get(factor_id, ""),
        }
        if factor_type is not None:
            info["factor_type"] = factor_type
            info["factor_type_name"] = FACTOR_TYPE_LABELS.get(
                factor_type,
                f"Type {factor_type}",
            )
        for key in optional:
            value = values.get(key)
            if value is not None:
                info[key] = value
        factors[factor_id] = info
    return factors


def _load_skills(
    connection: sqlite3.Connection,
    tables: set[str],
    *,
    names: dict[int, str],
    alternate_names: dict[int, str],
    descriptions: dict[int, str],
) -> dict[int, dict[str, Any]]:
    skills: dict[int, dict[str, Any]] = {}
    if "skill_data" in tables:
        columns = _table_columns(connection, "skill_data")
        id_column = "id" if "id" in columns else "skill_id" if "skill_id" in columns else ""
        if id_column:
            optional = [
                name
                for name in (
                    "rarity",
                    "group_id",
                    "icon_id",
                    "grade_value",
                    "skill_category",
                )
                if name in columns
            ]
            selection = ", ".join([id_column, *optional])
            for row in connection.execute(f"SELECT {selection} FROM skill_data"):
                values = dict(row)
                skill_id = _integer_or_none(values.get(id_column))
                if skill_id is None:
                    continue
                info: dict[str, Any] = {
                    "skill_id": skill_id,
                    "skill_name": names.get(skill_id)
                    or alternate_names.get(skill_id, ""),
                    "skill_description": descriptions.get(skill_id, ""),
                }
                for key in optional:
                    value = values.get(key)
                    if value is not None:
                        info[key] = value
                skills[skill_id] = info

    # Some historical/current variants expose text rows even when skill_data is
    # absent or incomplete. Keep those names usable without inventing metadata.
    for skill_id, name in names.items():
        skills.setdefault(
            skill_id,
            {
                "skill_id": skill_id,
                "skill_name": name,
                "skill_description": descriptions.get(skill_id, ""),
            },
        )
    return skills


def _resolve_record(
    record: dict[str, Any],
    cards: dict[int, dict[str, Any]],
    factors: dict[int, dict[str, Any]],
    skills: dict[int, dict[str, Any]],
    counts: dict[str, int],
) -> dict[str, Any]:
    card_id = _integer_or_none(_first(record, "card_id", "cardId"))
    if card_id is not None:
        card = cards.get(card_id)
        if card is None:
            counts["unresolved_cards"] += 1
        else:
            counts["card_records"] += 1
            if not _first(
                record,
                "name",
                "chara_name",
                "character_name",
                "card_name",
                "trained_chara_name",
            ):
                display_name = card.get("card_name") or card.get("chara_name")
                if display_name:
                    record["name"] = display_name
            for key in ("chara_id", "chara_name", "costume_name", "card_name"):
                value = card.get(key)
                if value not in (None, "") and record.get(key) in (None, ""):
                    record[key] = value

    raw_factors = _first(record, *_FACTOR_KEYS)
    resolved_factors: list[dict[str, Any]] = []
    if isinstance(raw_factors, (list, tuple)):
        for raw in raw_factors:
            item = dict(raw) if isinstance(raw, dict) else {"factor_id": raw}
            factor_id = _integer_or_none(
                _first(item, "factor_id", "factorId", "id")
            )
            if factor_id is None:
                resolved_factors.append(item)
                continue
            item.setdefault("factor_id", factor_id)
            info = factors.get(factor_id)
            if info is None:
                counts["unresolved_factors"] += 1
            else:
                counts["factor_entries"] += 1
                for key, value in info.items():
                    if value not in (None, "") and item.get(key) in (None, ""):
                        item[key] = value
                if item.get("level") in (None, "") and info.get("rarity") is not None:
                    item["level"] = info["rarity"]
            resolved_factors.append(item)
    if resolved_factors:
        record["factor_info_array"] = resolved_factors

    raw_skills = _first(record, *_SKILL_KEYS)
    resolved_skills: list[dict[str, Any]] = []
    if isinstance(raw_skills, (list, tuple)):
        for raw in raw_skills:
            item = dict(raw) if isinstance(raw, dict) else {"skill_id": raw}
            skill_id = _integer_or_none(_first(item, "skill_id", "skillId", "id"))
            if skill_id is None:
                resolved_skills.append(item)
                continue
            item.setdefault("skill_id", skill_id)
            info = skills.get(skill_id)
            if info is None:
                counts["unresolved_skills"] += 1
            else:
                counts["skill_entries"] += 1
                for key, value in info.items():
                    if value not in (None, "") and item.get(key) in (None, ""):
                        item[key] = value
            resolved_skills.append(item)
    if resolved_skills:
        record["skill_array"] = resolved_skills

    return record


def _app_value(app: Any, attribute: str) -> str:
    value = getattr(app, attribute, "")
    try:
        value = value.get()
    except (AttributeError, TypeError):
        pass
    return _text(value)


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _integer_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""

from __future__ import annotations

import csv
import json
import os
import shutil
import stat
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .safety import atomic_write_json, hash_file

VETERAN_STORE_VERSION = 1
MAX_ROSTER_BYTES = 128 * 1024 * 1024
MAX_VETERANS = 100_000
PRIVATE_FIELDS = {"viewer_id", "owner_viewer_id"}
UPSTREAM_PROJECT = "NECOtype/UmaExtractor"
UPSTREAM_URL = "https://github.com/NECOtype/UmaExtractor"
UPSTREAM_FORMAT = "UmaExtractor data.json"


class VeteranDataError(RuntimeError):
    """Raised when an imported veteran roster is unsafe or malformed."""


@dataclass(frozen=True)
class VeteranSnapshot:
    id: str
    imported_at: str
    source_name: str
    source_sha256: str
    record_count: int
    data_file: str
    provider: str = UPSTREAM_PROJECT
    provider_url: str = UPSTREAM_URL
    license_status: str = "not-declared"
    warnings: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VeteranSnapshot":
        if not isinstance(value, dict):
            raise VeteranDataError("Veteran snapshot metadata must be an object")
        snapshot_id = str(value.get("id") or "").strip()
        data_file = str(value.get("data_file") or "").strip()
        if not snapshot_id or not data_file:
            raise VeteranDataError("Veteran snapshot metadata is incomplete")
        raw_warnings = value.get("warnings", [])
        warnings = tuple(str(item) for item in raw_warnings) if isinstance(raw_warnings, list) else ()
        return cls(
            id=snapshot_id,
            imported_at=str(value.get("imported_at") or ""),
            source_name=str(value.get("source_name") or "data.json"),
            source_sha256=str(value.get("source_sha256") or ""),
            record_count=int(value.get("record_count") or 0),
            data_file=data_file,
            provider=str(value.get("provider") or UPSTREAM_PROJECT),
            provider_url=str(value.get("provider_url") or UPSTREAM_URL),
            license_status=str(value.get("license_status") or "not-declared"),
            warnings=warnings,
        )


@dataclass(frozen=True)
class VeteranRow:
    index: int
    name: str
    chara_id: str
    card_id: str
    rank: str
    speed: int
    stamina: int
    power: int
    guts: int
    wisdom: int
    factor_count: int
    skill_count: int
    search_text: str

    @property
    def total_stats(self) -> int:
        return self.speed + self.stamina + self.power + self.guts + self.wisdom


class VeteranStore:
    """Private local snapshot store for externally extracted veteran rosters.

    This class does not attach to or inspect the game process. It only accepts
    already-produced JSON, validates it, removes known account identifiers, and
    stores immutable snapshots below the Manager data root.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser()
        self.snapshots_dir = self.root / "snapshots"
        self.index_path = self.root / "index.json"
        self.settings_path = self.root / "settings.json"
        self.inbox = self.root / "inbox"
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.inbox.mkdir(parents=True, exist_ok=True)

    def list_snapshots(self) -> list[VeteranSnapshot]:
        document = self._read_index()
        raw = document.get("snapshots", [])
        if not isinstance(raw, list):
            raise VeteranDataError(f"Veteran snapshot index is malformed: {self.index_path}")
        snapshots = [VeteranSnapshot.from_dict(item) for item in raw]
        snapshots.sort(key=lambda item: item.imported_at, reverse=True)
        return snapshots

    def get_snapshot(self, snapshot_id: str) -> VeteranSnapshot:
        for snapshot in self.list_snapshots():
            if snapshot.id == snapshot_id:
                return snapshot
        raise VeteranDataError(f"Unknown veteran snapshot: {snapshot_id}")

    def import_json(self, source: str | Path) -> VeteranSnapshot:
        source_path = Path(source).expanduser().resolve()
        self._validate_source_file(source_path)
        source_sha256 = hash_file(source_path)

        for existing in self.list_snapshots():
            if existing.source_sha256 == source_sha256:
                return existing

        try:
            raw = json.loads(source_path.read_text(encoding="utf-8-sig"))
        except UnicodeDecodeError as exc:
            raise VeteranDataError("Veteran roster must be UTF-8 JSON") from exc
        except json.JSONDecodeError as exc:
            raise VeteranDataError(
                f"Veteran roster is not valid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
            ) from exc
        except OSError as exc:
            raise VeteranDataError(f"Could not read veteran roster: {exc}") from exc

        records = _extract_record_list(raw)
        if len(records) > MAX_VETERANS:
            raise VeteranDataError(
                f"Veteran roster contains {len(records):,} entries; the safety limit is {MAX_VETERANS:,}"
            )

        cleaned: list[dict[str, Any]] = []
        stripped_fields = 0
        missing_identity = 0
        duplicate_records = 0
        seen_records: set[str] = set()
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise VeteranDataError(f"Veteran entry {index + 1} is not an object")
            scrubbed, stripped = _scrub_private_fields(record)
            stripped_fields += stripped
            if not _first(scrubbed, "trained_chara_id", "trained_chara_data_id", "card_id", "chara_id"):
                missing_identity += 1
            canonical = json.dumps(scrubbed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            if canonical in seen_records:
                duplicate_records += 1
            else:
                seen_records.add(canonical)
            cleaned.append(scrubbed)

        warnings: list[str] = []
        if stripped_fields:
            warnings.append(
                f"Removed {stripped_fields} viewer/account identifier field(s) before storage."
            )
        if missing_identity:
            warnings.append(
                f"{missing_identity} record(s) did not expose a recognized card or character identifier."
            )
        if duplicate_records:
            warnings.append(
                f"Detected {duplicate_records} exact duplicate record(s); they were preserved for provenance."
            )

        imported_at = datetime.now(timezone.utc).isoformat()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_id = f"{stamp}-{source_sha256[:12]}"
        data_name = f"{snapshot_id}.json"
        data_path = self.snapshots_dir / data_name
        payload = {
            "schema_version": VETERAN_STORE_VERSION,
            "provenance": {
                "provider": UPSTREAM_PROJECT,
                "provider_url": UPSTREAM_URL,
                "format": UPSTREAM_FORMAT,
                "license_status": "not-declared",
                "source_name": source_path.name,
                "source_sha256": source_sha256,
                "imported_at": imported_at,
                "privacy_fields_removed": stripped_fields,
            },
            "warnings": warnings,
            "records": cleaned,
        }
        atomic_write_json(data_path, payload)

        snapshot = VeteranSnapshot(
            id=snapshot_id,
            imported_at=imported_at,
            source_name=source_path.name,
            source_sha256=source_sha256,
            record_count=len(cleaned),
            data_file=data_name,
            warnings=tuple(warnings),
        )
        index = self._read_index()
        existing = index.get("snapshots", [])
        if not isinstance(existing, list):
            raise VeteranDataError(f"Veteran snapshot index is malformed: {self.index_path}")
        existing.append(asdict(snapshot))
        index["version"] = VETERAN_STORE_VERSION
        index["snapshots"] = existing
        atomic_write_json(self.index_path, index)
        return snapshot

    def load_records(self, snapshot: VeteranSnapshot | str) -> list[dict[str, Any]]:
        value = self.get_snapshot(snapshot) if isinstance(snapshot, str) else snapshot
        data_path = self.snapshots_dir / value.data_file
        try:
            document = json.loads(data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VeteranDataError(f"Could not read veteran snapshot {value.id}: {exc}") from exc
        if not isinstance(document, dict):
            raise VeteranDataError(f"Veteran snapshot is malformed: {data_path}")
        records = document.get("records", [])
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise VeteranDataError(f"Veteran snapshot records are malformed: {data_path}")
        return [dict(item) for item in records]

    def export_snapshot(self, snapshot: VeteranSnapshot | str, destination: str | Path) -> Path:
        value = self.get_snapshot(snapshot) if isinstance(snapshot, str) else snapshot
        source = self.snapshots_dir / value.data_file
        target = Path(destination).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return target

    def export_csv(
        self,
        records: Iterable[dict[str, Any]],
        destination: str | Path,
    ) -> Path:
        target = Path(destination).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = [row_from_record(index, record) for index, record in enumerate(records)]
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "index",
                    "name",
                    "chara_id",
                    "card_id",
                    "rank",
                    "speed",
                    "stamina",
                    "power",
                    "guts",
                    "wisdom",
                    "total_stats",
                    "factor_count",
                    "skill_count",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.index,
                        row.name,
                        row.chara_id,
                        row.card_id,
                        row.rank,
                        row.speed,
                        row.stamina,
                        row.power,
                        row.guts,
                        row.wisdom,
                        row.total_stats,
                        row.factor_count,
                        row.skill_count,
                    ]
                )
        return target

    def load_settings(self) -> dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return dict(value) if isinstance(value, dict) else {}

    def save_settings(self, value: dict[str, Any]) -> None:
        atomic_write_json(self.settings_path, dict(value))

    def _read_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"version": VETERAN_STORE_VERSION, "snapshots": []}
        try:
            value = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VeteranDataError(f"Could not read veteran snapshot index: {exc}") from exc
        if not isinstance(value, dict):
            raise VeteranDataError(f"Veteran snapshot index is malformed: {self.index_path}")
        version = int(value.get("version") or 0)
        if version != VETERAN_STORE_VERSION:
            raise VeteranDataError(
                f"Unsupported veteran snapshot index version {version}; expected {VETERAN_STORE_VERSION}"
            )
        return dict(value)

    @staticmethod
    def _validate_source_file(path: Path) -> None:
        try:
            mode = path.lstat().st_mode
            size = path.stat().st_size
        except OSError as exc:
            raise VeteranDataError(f"Veteran roster file is unavailable: {path}: {exc}") from exc
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise VeteranDataError(f"Veteran roster must be a regular file: {path}")
        if size > MAX_ROSTER_BYTES:
            mib = size / (1024 * 1024)
            raise VeteranDataError(
                f"Veteran roster is {mib:.1f} MiB; the safety limit is {MAX_ROSTER_BYTES // (1024 * 1024)} MiB"
            )


def row_from_record(index: int, record: dict[str, Any]) -> VeteranRow:
    chara_id = _text(_first(record, "chara_id", "character_id"))
    card_id = _text(_first(record, "card_id", "cardId"))
    explicit_name = _text(
        _first(record, "name", "chara_name", "character_name", "card_name", "trained_chara_name")
    )
    if explicit_name:
        name = explicit_name
    elif chara_id and card_id:
        name = f"Character {chara_id} · Card {card_id}"
    elif chara_id:
        name = f"Character {chara_id}"
    elif card_id:
        name = f"Card {card_id}"
    else:
        name = f"Veteran #{index + 1}"

    search_text = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).casefold()
    return VeteranRow(
        index=index,
        name=name,
        chara_id=chara_id,
        card_id=card_id,
        rank=_text(_first(record, "rank", "rank_name", "evaluation", "evaluation_point")) or "—",
        speed=_integer(record.get("speed")),
        stamina=_integer(record.get("stamina")),
        power=_integer(record.get("power")),
        guts=_integer(record.get("guts")),
        wisdom=_integer(_first(record, "wiz", "wisdom", "intelligence")),
        factor_count=_sequence_count(_first(record, "factor_id_array", "factors", "factor_array")),
        skill_count=_sequence_count(_first(record, "skill_array", "skills", "skill_id_array")),
        search_text=search_text,
    )


def filter_rows(rows: Iterable[VeteranRow], query: str) -> list[VeteranRow]:
    tokens = [token for token in query.casefold().split() if token]
    if not tokens:
        return list(rows)
    return [row for row in rows if all(token in row.search_text or token in row.name.casefold() for token in tokens)]


def roster_summary(rows: Iterable[VeteranRow]) -> dict[str, int]:
    values = list(rows)
    unique_characters = {row.chara_id for row in values if row.chara_id}
    return {
        "count": len(values),
        "unique_characters": len(unique_characters),
        "best_total": max((row.total_stats for row in values), default=0),
        "factors": sum(row.factor_count for row in values),
        "skills": sum(row.skill_count for row in values),
    }


def record_detail(record: dict[str, Any], row: VeteranRow) -> str:
    lines = [
        row.name,
        f"Character ID: {row.chara_id or 'unknown'}",
        f"Card ID: {row.card_id or 'unknown'}",
        f"Rank/evaluation: {row.rank}",
        "",
        "Stats",
        f"  Speed {row.speed} · Stamina {row.stamina} · Power {row.power}",
        f"  Guts {row.guts} · Wisdom {row.wisdom} · Total {row.total_stats}",
        "",
        f"Factors: {row.factor_count}",
        f"Skills: {row.skill_count}",
    ]
    aptitudes = [
        (key, value)
        for key, value in record.items()
        if str(key).startswith("proper_") and value not in (None, "", 0)
    ]
    if aptitudes:
        lines.extend(["", "Aptitudes"])
        lines.extend(f"  {key.removeprefix('proper_').replace('_', ' ')}: {value}" for key, value in aptitudes)
    lines.extend(["", "Raw extracted record", json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False)])
    return "\n".join(lines)


def _extract_record_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("records", "veterans", "trained_chara_array", "data"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
    raise VeteranDataError(
        "Veteran roster JSON must contain an array or an object with records/veterans/trained_chara_array"
    )


def _scrub_private_fields(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        stripped = 0
        for key, item in value.items():
            if str(key).casefold() in PRIVATE_FIELDS:
                stripped += 1
                continue
            scrubbed, child_stripped = _scrub_private_fields(item)
            cleaned[str(key)] = scrubbed
            stripped += child_stripped
        return cleaned, stripped
    if isinstance(value, list):
        cleaned_list: list[Any] = []
        stripped = 0
        for item in value:
            scrubbed, child_stripped = _scrub_private_fields(item)
            cleaned_list.append(scrubbed)
            stripped += child_stripped
        return cleaned_list, stripped
    return value, 0


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value)


def _sequence_count(value: Any) -> int:
    if isinstance(value, (list, tuple, set, dict)):
        return len(value)
    return 0

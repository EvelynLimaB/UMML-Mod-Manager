from __future__ import annotations

import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import quote

from PIL import Image

from .veteran_master_data import discover_master_mdb


class LocalPortraitError(RuntimeError):
    """Raised when installed game artwork cannot be resolved safely."""


@dataclass(frozen=True)
class LocalPortraitResult:
    card_id: int
    portrait: Path | None
    cache_hit: bool = False
    logical_name: str = ""
    source_bundle: Path | None = None
    warning: str = ""


Extractor = Callable[[Path, tuple[str, ...], Path], bool]
_SAFE_ASSET_HASH = re.compile(r"^[0-9A-Fa-f]{8,128}$")


class LocalPortraitCache:
    """Read costume portraits from the user's own installed game data.

    ``master.mdb`` maps a card to its character and race dress. ``meta`` maps
    the logical asset name to a content hash, and ``dat`` contains the Unity
    bundle at ``dat/<first-two-hash-characters>/<hash>``. Only Manager-owned PNG
    cache files are written; all game databases and bundles remain read-only.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        master_path: str | Path | None,
        meta_path: str | Path | None,
        dat_root: str | Path | None,
        extractor: Extractor | None = None,
    ):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.master_path = _path_or_none(master_path)
        self.meta_path = _path_or_none(meta_path)
        self.dat_root = _path_or_none(dat_root)
        self.extractor = extractor or _extract_unity_portrait

    @classmethod
    def from_app(cls, app: Any, root: str | Path) -> "LocalPortraitCache":
        master = discover_master_mdb(app)
        persistent: Path | None = master.parent.parent if master else None

        meta_value = _app_value(app, "meta_path")
        dat_value = _app_value(app, "dat_path")
        meta = Path(meta_value).expanduser() if meta_value else None
        dat = Path(dat_value).expanduser() if dat_value else None

        if persistent is not None:
            if meta is None or not meta.is_file():
                meta = persistent / "meta"
            if dat is None or not dat.is_dir():
                dat = persistent / "dat"

        return cls(
            root,
            master_path=master,
            meta_path=meta,
            dat_root=dat,
        )

    @property
    def available(self) -> bool:
        return bool(
            self.master_path
            and self.master_path.is_file()
            and self.meta_path
            and self.meta_path.is_file()
            and self.dat_root
            and self.dat_root.is_dir()
        )

    def cached(self, card_id: object) -> Path | None:
        resolved = _positive_integer(card_id)
        if resolved is None:
            return None
        candidate = self.root / f"local-portrait-{resolved}.png"
        return candidate if candidate.is_file() else None

    def extract(self, card_id: object) -> LocalPortraitResult:
        resolved = _positive_integer(card_id)
        if resolved is None:
            return LocalPortraitResult(0, None, warning="Card ID is not a positive integer.")

        cached = self.cached(resolved)
        if cached is not None:
            return LocalPortraitResult(resolved, cached, cache_hit=True)
        if not self.available:
            return LocalPortraitResult(
                resolved,
                None,
                warning="The installed master, meta, or dat path is unavailable.",
            )

        try:
            stems = self._portrait_stems(resolved)
            candidates = self._bundle_candidates(stems)
        except (sqlite3.Error, OSError, LocalPortraitError) as exc:
            return LocalPortraitResult(resolved, None, warning=str(exc))

        target = self.root / f"local-portrait-{resolved}.png"
        warnings: list[str] = []
        for logical_name, content_hash in candidates:
            bundle = self._bundle_path(content_hash)
            if bundle is None:
                warnings.append(f"Asset hash {content_hash!r} is invalid or absent from dat.")
                continue
            try:
                if self.extractor(bundle, stems, target) and target.is_file():
                    return LocalPortraitResult(
                        resolved,
                        target,
                        logical_name=logical_name,
                        source_bundle=bundle,
                    )
            except Exception as exc:
                warnings.append(f"{logical_name}: {exc}")

        warning = " ".join(warnings[:3])
        if not warning:
            warning = "No matching installed costume portrait was found in meta/dat."
        return LocalPortraitResult(resolved, None, warning=warning)

    def extract_many(
        self,
        card_ids: Iterable[object],
    ) -> tuple[LocalPortraitResult, ...]:
        seen: set[int] = set()
        results: list[LocalPortraitResult] = []
        for raw in card_ids:
            card_id = _positive_integer(raw)
            if card_id is None or card_id in seen:
                continue
            seen.add(card_id)
            results.append(self.extract(card_id))
        return tuple(results)

    def _portrait_stems(self, card_id: int) -> tuple[str, ...]:
        if self.master_path is None:
            raise LocalPortraitError("master.mdb is unavailable.")
        connection = _open_read_only(self.master_path)
        try:
            card_columns = _columns(connection, "card_data")
            if not {"id", "chara_id"}.issubset(card_columns):
                raise LocalPortraitError("card_data does not expose id and chara_id.")
            row = connection.execute(
                "SELECT chara_id FROM card_data WHERE id = ? LIMIT 1",
                (card_id,),
            ).fetchone()
            if row is None:
                raise LocalPortraitError(f"Card {card_id} is absent from card_data.")
            chara_id = _positive_integer(row[0])
            if chara_id is None:
                raise LocalPortraitError(f"Card {card_id} has no valid character ID.")

            dress_id: int | None = None
            rarity_columns = _columns(connection, "card_rarity_data")
            if {"card_id", "race_dress_id"}.issubset(rarity_columns):
                order = (
                    "CASE WHEN rarity = 3 THEN 0 ELSE 1 END, rarity DESC"
                    if "rarity" in rarity_columns
                    else "rowid"
                )
                dress_row = connection.execute(
                    "SELECT race_dress_id FROM card_rarity_data "
                    f"WHERE card_id = ? ORDER BY {order} LIMIT 1",
                    (card_id,),
                ).fetchone()
                if dress_row is not None:
                    dress_id = _positive_integer(dress_row[0])

            stems: list[str] = []
            if dress_id is not None:
                stems.append(f"chara_stand_{chara_id}_{dress_id:06d}")
            stems.append(f"chara_stand_{chara_id}_{card_id:06d}")
            return tuple(dict.fromkeys(stems))
        finally:
            connection.close()

    def _bundle_candidates(self, stems: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
        if self.meta_path is None:
            raise LocalPortraitError("meta is unavailable.")
        connection = _open_read_only(self.meta_path)
        try:
            columns = _columns(connection, "a")
            if not {"n", "h"}.issubset(columns):
                raise LocalPortraitError("The meta database has no a(n, h) asset map.")
            found: list[tuple[str, str]] = []
            seen: set[str] = set()
            for stem in stems:
                escaped = _escape_like(stem)
                rows = connection.execute(
                    "SELECT n, h FROM a WHERE n LIKE ? ESCAPE '\\' ORDER BY n LIMIT 32",
                    (f"%{escaped}%",),
                )
                for logical_name, content_hash in rows:
                    logical = str(logical_name or "")
                    digest = str(content_hash or "").strip()
                    if not _safe_asset_hash(digest) or digest in seen:
                        continue
                    seen.add(digest)
                    found.append((logical, digest))
            return tuple(found)
        finally:
            connection.close()

    def _bundle_path(self, content_hash: str) -> Path | None:
        if self.dat_root is None:
            return None
        digest = str(content_hash).strip()
        if not _safe_asset_hash(digest):
            return None

        try:
            root = self.dat_root.resolve(strict=True)
        except OSError:
            return None
        prefixes = tuple(dict.fromkeys((digest[:2], digest[:2].lower(), digest[:2].upper())))
        candidates = [root / prefix / digest for prefix in prefixes]
        candidates.append(root / digest)
        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                continue
            if not _is_relative_to(resolved, root):
                continue
            if resolved.is_file():
                return resolved
        return None


def _extract_unity_portrait(
    bundle: Path,
    stems: tuple[str, ...],
    target: Path,
) -> bool:
    try:
        import UnityPy
    except ImportError as exc:
        raise LocalPortraitError("UnityPy is not available in this build.") from exc

    environment = UnityPy.load(str(bundle))
    normalized_stems = tuple(stem.casefold() for stem in stems)
    candidates: list[tuple[int, int, Any]] = []
    seen_objects: set[int] = set()

    def consider(reader: Any, container_path: str = "") -> None:
        identifier = int(getattr(reader, "path_id", id(reader)))
        if identifier in seen_objects:
            return
        seen_objects.add(identifier)
        type_name = str(getattr(getattr(reader, "type", None), "name", ""))
        if type_name not in {"Sprite", "Texture2D"}:
            return
        data = reader.parse_as_object()
        name = str(getattr(data, "m_Name", ""))
        corpus = f"{container_path} {name}".casefold()
        exact = any(stem in corpus for stem in normalized_stems)
        width = int(getattr(data, "m_Width", 0) or 0)
        height = int(getattr(data, "m_Height", 0) or 0)
        score = (100 if exact else 0) + (20 if type_name == "Sprite" else 0)
        candidates.append((score, max(0, width * height), data))

    for container_path, reader in getattr(environment, "container", {}).items():
        consider(reader, str(container_path))
    for reader in getattr(environment, "objects", ()):
        consider(reader)

    if not candidates:
        return False
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best_score, _area, data = candidates[0]
    if best_score < 100 and len(candidates) > 1:
        # A bundle selected by an exact logical path can still use a generic
        # object name, but do not guess among several unrelated textures.
        return False

    image = data.image.convert("RGBA")
    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
    _atomic_save(image, target)
    return True


def _atomic_save(image: Image.Image, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        image.save(temporary, format="PNG", optimize=True)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _open_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    uri_path = quote(resolved.as_posix(), safe="/:")
    connection = sqlite3.connect(
        f"file:{uri_path}?mode=ro",
        uri=True,
        timeout=5,
    )
    connection.execute("PRAGMA query_only = ON")
    return connection


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    safe = table.replace('"', '""')
    try:
        return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{safe}")')}
    except sqlite3.Error:
        return set()


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _safe_asset_hash(value: str) -> bool:
    return bool(_SAFE_ASSET_HASH.fullmatch(value))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _path_or_none(value: str | Path | None) -> Path | None:
    if value in (None, ""):
        return None
    return Path(value).expanduser()


def _app_value(app: Any, attribute: str) -> str:
    value = getattr(app, attribute, "")
    getter = getattr(value, "get", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:
            return ""
    return str(value or "").strip()


def _positive_integer(value: object) -> int | None:
    try:
        integer = int(value)
    except (TypeError, ValueError):
        return None
    return integer if integer > 0 else None

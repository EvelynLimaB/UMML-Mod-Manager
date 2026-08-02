from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import urllib.parse
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable

from ..legacy_archive import import_loose_legacy_archive
from ..library import ManagerStore, UnrecognizedModError
from ..regions import region_from_game_name
from ..store import StoreError
from .gamebanana import (
    GameBananaClient,
    GameBananaFile,
    GameBananaMod,
    GameBananaPage,
)

CACHE_VERSION = 1
CACHE_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
TRANSIENT_RETRY_DELAYS = (0.0, 0.5, 1.5)
CORE_DETAIL_FIELDS = (
    "name",
    "Owner().name",
    "Url().sProfileUrl()",
    "text",
    "date",
    "mdate",
    "views",
    "likes",
    "downloads",
    "Preview().sSubFeedImageUrl()",
    "RootCategory().name",
    "Game().name",
    "is_obsolete",
    "Files().aFiles()",
)


class PreviewGameBananaClient(GameBananaClient):
    """Interactive GameBanana client with bounded provider resilience.

    GameBanana occasionally returns 5xx responses from one or both public API
    hosts. Interactive browsing therefore retries transient failures, switches
    from the v11 API to the independent Core API for detail records, and falls
    back to bounded persistent cache data instead of turning Discover into an
    empty modal error. Providers still never deploy game files.
    """

    def __init__(
        self,
        opener: Callable[..., Any] | None = None,
        *,
        cache_root: str | Path | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ):
        super().__init__(opener=opener)
        self.cache_root = Path(
            cache_root or _default_cache_root()
        ).expanduser()
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self._sleep = sleeper
        self._clock = clock
        self._apiv11_unavailable_until = 0.0
        self.last_notice = ""

    def browse(
        self,
        *,
        region: str = "global",
        page: int = 1,
        per_page: int = 24,
        sort: str = "updated",
        query: str = "",
    ) -> GameBananaPage:
        parameters = {
            "region": region.casefold(),
            "page": max(1, int(page)),
            "per_page": max(1, min(50, int(per_page))),
            "sort": sort.casefold(),
            "query": query.strip(),
        }
        self.last_notice = ""
        try:
            result = super().browse(**parameters)
        except StoreError as error:
            cached = self._read_page_cache(parameters)
            if cached is not None:
                self.last_notice = (
                    "GameBanana is temporarily unavailable; showing the most "
                    "recent cached results for this page."
                )
                return cached
            raise StoreError(
                _friendly_unavailable_message(error)
            ) from error
        self._write_page_cache(parameters, result)
        return result

    def fetch(self, value: str) -> GameBananaMod:
        mod_id = self.parse_mod_id(value)
        primary_error: StoreError | None = None
        if self._clock() >= self._apiv11_unavailable_until:
            try:
                result = super().fetch(str(mod_id))
            except StoreError as error:
                primary_error = error
            else:
                self._write_mod_cache(result)
                return result
        try:
            result = self._fetch_core(mod_id)
        except StoreError as fallback_error:
            cached = self._read_mod_cache(mod_id)
            if cached is not None:
                self.last_notice = (
                    "GameBanana detail endpoints are unavailable; using "
                    f"cached metadata for mod {mod_id}."
                )
                return cached
            if primary_error is None:
                raise StoreError(
                    _friendly_unavailable_message(fallback_error)
                ) from fallback_error
            raise StoreError(
                "GameBanana's v11 and Core detail endpoints both failed.\n"
                f"v11: {primary_error}\nCore: {fallback_error}"
            ) from fallback_error
        self._write_mod_cache(result)
        return result

    def download(self, *args, **kwargs):
        last_error: StoreError | None = None
        for attempt, delay in enumerate(TRANSIENT_RETRY_DELAYS):
            if delay:
                self._sleep(delay)
            try:
                return super().download(*args, **kwargs)
            except StoreError as error:
                last_error = error
                final_attempt = attempt + 1 >= len(
                    TRANSIENT_RETRY_DELAYS
                )
                if not _is_transient_error(error) or final_attempt:
                    break
        assert last_error is not None
        if _is_transient_error(last_error):
            raise StoreError(
                "GameBanana temporarily refused the file download after "
                "three attempts. The partial file was removed and no mod was "
                "imported. Retry later or import a manually downloaded "
                "archive.\n"
                f"Last error: {last_error}"
            ) from last_error
        raise last_error

    def _request_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        is_v11 = endpoint.startswith(
            "https://gamebanana.com/apiv11/"
        )
        if (
            is_v11
            and self._clock() < self._apiv11_unavailable_until
        ):
            raise StoreError(
                "GameBanana v11 API is temporarily unavailable "
                "(circuit open)"
            )
        last_error: StoreError | None = None
        for attempt, delay in enumerate(TRANSIENT_RETRY_DELAYS):
            if delay:
                self._sleep(delay)
            try:
                value = super()._request_json(endpoint, params)
            except StoreError as error:
                last_error = error
                final_attempt = attempt + 1 >= len(
                    TRANSIENT_RETRY_DELAYS
                )
                if not _is_transient_error(error) or final_attempt:
                    break
            else:
                if is_v11:
                    self._apiv11_unavailable_until = 0.0
                return value
        assert last_error is not None
        if is_v11 and _is_transient_error(last_error):
            self._apiv11_unavailable_until = self._clock() + 120.0
        raise last_error

    def _fetch_core(self, mod_id: int) -> GameBananaMod:
        values = self._request_json(
            "https://api.gamebanana.com/Core/Item/Data",
            {
                "itemtype": "Mod",
                "itemid": mod_id,
                "fields": ",".join(CORE_DETAIL_FIELDS),
                "return_keys": 1,
                "format": "json_min",
            },
        )
        if isinstance(values, dict) and values.get("error"):
            raise StoreError(
                f"GameBanana Core API: {values.get('error')}"
            )
        if isinstance(values, dict):
            data = {
                field: values.get(field)
                for field in CORE_DETAIL_FIELDS
            }
        elif (
            isinstance(values, list)
            and len(values) >= len(CORE_DETAIL_FIELDS)
        ):
            data = dict(
                zip(CORE_DETAIL_FIELDS, values, strict=False)
            )
        else:
            raise StoreError(
                "GameBanana Core API returned an unexpected detail response"
            )

        files = tuple(
            self._file(item)
            for item in _core_file_records(
                data.get("Files().aFiles()")
            )
        )
        image_url = str(
            data.get("Preview().sSubFeedImageUrl()") or ""
        ).strip()
        return GameBananaMod(
            id=mod_id,
            name=str(
                data.get("name")
                or f"GameBanana mod {mod_id}"
            ),
            author=str(data.get("Owner().name") or ""),
            profile_url=str(
                data.get("Url().sProfileUrl()")
                or f"https://gamebanana.com/mods/{mod_id}"
            ),
            files=files,
            description=_plain_text(str(data.get("text") or "")),
            date_added=_integer(data.get("date")),
            date_updated=_integer(data.get("mdate")),
            views=_integer(data.get("views")),
            likes=_integer(data.get("likes")),
            downloads=(
                _integer(data.get("downloads"))
                or sum(item.downloads for item in files)
            ),
            image_url=(
                image_url
                if _verified_gamebanana_https(image_url)
                else ""
            ),
            category=str(data.get("RootCategory().name") or ""),
            game_name=str(data.get("Game().name") or ""),
            obsolete=bool(data.get("is_obsolete")),
        )

    def _mod(
        self,
        data: dict[str, Any],
        fallback_id: int = 0,
    ) -> GameBananaMod:
        normalized = dict(data)
        normalized["_aFiles"] = normalize_file_records(
            data.get("_aFiles")
        )
        mod = super()._mod(
            normalized,
            fallback_id=fallback_id,
        )
        return replace(
            mod,
            image_url=primary_preview_url(data),
        )

    def import_mod(
        self,
        store: ManagerStore,
        value: str,
        *,
        file_id: int | None = None,
    ):
        mod = self.fetch(value)
        archive, source = self.download(
            mod,
            store.paths.root / "downloads",
            file_id=file_id,
        )
        region = region_from_game_name(mod.game_name)
        metadata = {
            "title": mod.name,
            "author": mod.author,
            "description": mod.description,
            "mod_version": mod.version or str(source.file_id or 0),
            "regions": [region] if region else [],
        }
        record_id = f"gamebanana-{mod.id}"
        try:
            return store.import_archive(
                archive,
                mod_id=record_id,
                source=source,
                metadata_overrides=metadata,
            )
        except UnrecognizedModError:
            return import_loose_legacy_archive(
                store,
                archive,
                mod_id=record_id,
                source=source,
                metadata_overrides=metadata,
            )

    def _page_cache_path(
        self,
        parameters: dict[str, Any],
    ) -> Path:
        encoded = json.dumps(
            parameters,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        return self.cache_root / f"page-{digest}.json"

    def _mod_cache_path(self, mod_id: int) -> Path:
        return self.cache_root / f"mod-{mod_id}.json"

    def _write_page_cache(
        self,
        parameters: dict[str, Any],
        page: GameBananaPage,
    ) -> None:
        self._write_cache(
            self._page_cache_path(parameters),
            {
                "version": CACHE_VERSION,
                "saved_at": self._clock(),
                "parameters": parameters,
                "page": {
                    "page": page.page,
                    "total": page.total,
                    "has_more": page.has_more,
                    "mods": [
                        _mod_to_dict(item)
                        for item in page.mods
                    ],
                },
            },
        )

    def _read_page_cache(
        self,
        parameters: dict[str, Any],
    ) -> GameBananaPage | None:
        value = self._read_cache(
            self._page_cache_path(parameters)
        )
        if not value:
            return None
        page = value.get("page")
        if not isinstance(page, dict):
            return None
        try:
            mods = tuple(
                _mod_from_dict(item)
                for item in page.get("mods", [])
            )
            return GameBananaPage(
                mods=mods,
                page=max(
                    1,
                    int(page.get("page") or parameters["page"]),
                ),
                total=max(0, int(page.get("total") or 0)),
                has_more=bool(page.get("has_more")),
            )
        except (TypeError, ValueError, StoreError):
            return None

    def _write_mod_cache(self, mod: GameBananaMod) -> None:
        self._write_cache(
            self._mod_cache_path(mod.id),
            {
                "version": CACHE_VERSION,
                "saved_at": self._clock(),
                "mod": _mod_to_dict(mod),
            },
        )

    def _read_mod_cache(
        self,
        mod_id: int,
    ) -> GameBananaMod | None:
        value = self._read_cache(self._mod_cache_path(mod_id))
        if not value or not isinstance(value.get("mod"), dict):
            return None
        try:
            return _mod_from_dict(value["mod"])
        except (TypeError, ValueError, StoreError):
            return None

    def _write_cache(
        self,
        path: Path,
        value: dict[str, Any],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(
                descriptor,
                "w",
                encoding="utf-8",
            ) as stream:
                json.dump(
                    value,
                    stream,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        try:
            if (
                path.is_symlink()
                or not path.is_file()
                or path.stat().st_size > 16 * 1024 * 1024
            ):
                return None
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(value, dict)
            or value.get("version") != CACHE_VERSION
        ):
            return None
        saved_at = float(value.get("saved_at") or 0.0)
        if (
            saved_at <= 0
            or self._clock() - saved_at > CACHE_MAX_AGE_SECONDS
        ):
            return None
        return value


def normalize_file_records(value: Any) -> list[dict[str, Any]]:
    """Normalize current, legacy, and Core API file containers."""

    if isinstance(value, (list, tuple)):
        return [
            dict(item)
            for item in value
            if isinstance(item, dict)
            and _looks_like_file_record(item)
        ]
    if not isinstance(value, dict):
        return []
    if _looks_like_file_record(value):
        return [dict(value)]
    mapped = _core_file_records(value)
    if mapped:
        return mapped
    for key in ("_aFiles", "files", "items", "records", "data"):
        if key in value:
            nested = normalize_file_records(value[key])
            if nested:
                return nested
    return [
        dict(item)
        for item in value.values()
        if isinstance(item, dict)
        and _looks_like_file_record(item)
    ]


def _core_file_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                result.extend(_core_file_records(item))
        return result
    if not isinstance(value, dict):
        return []
    result = []
    for key, item in value.items():
        if isinstance(item, dict):
            if _looks_like_file_record(item):
                result.append(dict(item))
            else:
                result.extend(_core_file_records(item))
            continue
        url = str(key).strip()
        name = str(item or "").strip()
        if not url.startswith("https://") or not name:
            continue
        path = urllib.parse.urlparse(url).path
        match = re.search(
            r"/(?:dl|download)/(\d+)(?:/|$)",
            path,
        )
        file_id = int(match.group(1)) if match else 0
        result.append(
            {
                "_idRow": file_id,
                "_sFile": name,
                "_sDownloadUrl": url,
            }
        )
    return result


def _looks_like_file_record(value: dict[str, Any]) -> bool:
    return any(
        value.get(key) not in (None, "")
        for key in (
            "_idRow",
            "_idFile",
            "_sDownloadUrl",
            "_sDownloadUrlArchive",
            "_sFile",
        )
    )


def primary_preview_url(data: dict[str, Any]) -> str:
    preview = data.get("_aPreviewMedia") or {}
    images = (
        preview.get("_aImages")
        if isinstance(preview, dict)
        else []
    )
    if not isinstance(images, list):
        return ""
    for item in images:
        if not isinstance(item, dict):
            continue
        base_url = str(item.get("_sBaseUrl") or "").strip()
        if not base_url:
            continue
        for field in (
            "_sFile530",
            "_sFile220",
            "_sFile100",
            "_sFile",
        ):
            filename = str(item.get(field) or "").strip()
            if not filename:
                continue
            url = urllib.parse.urljoin(
                base_url.rstrip("/") + "/",
                filename.lstrip("/"),
            )
            if _verified_gamebanana_https(url):
                return url
    return ""


def _verified_gamebanana_https(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").casefold()
    return bool(
        parsed.scheme.casefold() == "https"
        and hostname
        and (
            hostname == "gamebanana.com"
            or hostname.endswith(".gamebanana.com")
        )
    )


def _mod_to_dict(mod: GameBananaMod) -> dict[str, Any]:
    return asdict(mod)


def _mod_from_dict(value: dict[str, Any]) -> GameBananaMod:
    if not isinstance(value, dict):
        raise StoreError("Cached GameBanana mod is malformed")
    files = tuple(
        GameBananaFile(
            id=_integer(item.get("id")),
            name=str(item.get("name") or ""),
            url=str(item.get("url") or ""),
            date_added=_integer(item.get("date_added")),
            downloads=_integer(item.get("downloads")),
        )
        for item in value.get("files", [])
        if isinstance(item, dict)
    )
    return GameBananaMod(
        id=_integer(value.get("id")),
        name=str(value.get("name") or ""),
        author=str(value.get("author") or ""),
        profile_url=str(value.get("profile_url") or ""),
        files=files,
        description=str(value.get("description") or ""),
        version=str(value.get("version") or ""),
        date_added=_integer(value.get("date_added")),
        date_updated=_integer(value.get("date_updated")),
        views=_integer(value.get("views")),
        likes=_integer(value.get("likes")),
        downloads=_integer(value.get("downloads")),
        image_url=str(value.get("image_url") or ""),
        category=str(value.get("category") or ""),
        game_name=str(value.get("game_name") or ""),
        obsolete=bool(value.get("obsolete")),
    )


def _default_cache_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get(
            "APPDATA"
        )
        if base:
            return (
                Path(base).expanduser()
                / "UMML Manager"
                / "cache"
                / "gamebanana"
            )
        return (
            Path.home()
            / "AppData"
            / "Local"
            / "UMML Manager"
            / "cache"
            / "gamebanana"
        )
    base = os.environ.get("XDG_CACHE_HOME")
    cache = Path(base).expanduser() if base else Path.home() / ".cache"
    return cache / "uma-mod-manager" / "gamebanana"


def _is_transient_error(error: Exception) -> bool:
    message = " ".join(str(error).casefold().split())
    markers = (
        "http error 429",
        "http error 500",
        "http error 502",
        "http error 503",
        "http error 504",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "temporary failure",
        "connection reset",
        "remote end closed",
        "name or service not known",
    )
    return any(marker in message for marker in markers)


def _friendly_unavailable_message(error: Exception) -> str:
    message = " ".join(str(error).split())
    if _is_transient_error(error):
        return (
            "GameBanana is temporarily unavailable. The Manager retried the "
            "official v11 and Core API paths, but neither returned usable "
            "data. Retry later, or import a mod archive that you downloaded "
            "manually. No game files were changed.\n\n"
            f"Last provider error: {message}"
        )
    return (
        "GameBanana request failed safely. No game files were changed.\n\n"
        f"{message}"
    )


def _plain_text(value: str) -> str:
    import html

    value = re.sub(
        r"<br\s*/?>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(
        r"\n{3,}",
        "\n\n",
        html.unescape(value),
    ).strip()


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

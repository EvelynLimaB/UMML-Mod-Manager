from __future__ import annotations

import urllib.parse
from dataclasses import replace
from typing import Any

from ..legacy_archive import import_loose_legacy_archive
from ..library import ManagerStore, UnrecognizedModError
from ..regions import region_from_game_name
from .gamebanana import GameBananaClient, GameBananaMod


class PreviewGameBananaClient(GameBananaClient):
    """GameBanana client variant used by interactive/provider-aware frontends."""

    def _mod(self, data: dict[str, Any], fallback_id: int = 0) -> GameBananaMod:
        normalized = dict(data)
        normalized["_aFiles"] = normalize_file_records(data.get("_aFiles"))
        mod = super()._mod(normalized, fallback_id=fallback_id)
        return replace(mod, image_url=primary_preview_url(data))

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


def normalize_file_records(value: Any) -> list[dict[str, Any]]:
    """Normalize current and legacy GameBanana file containers."""

    if isinstance(value, (list, tuple)):
        return [
            dict(item)
            for item in value
            if isinstance(item, dict) and _looks_like_file_record(item)
        ]
    if not isinstance(value, dict):
        return []
    if _looks_like_file_record(value):
        return [dict(value)]
    for key in ("_aFiles", "files", "items", "records", "data"):
        if key in value:
            nested = normalize_file_records(value[key])
            if nested:
                return nested
    return [
        dict(item)
        for item in value.values()
        if isinstance(item, dict) and _looks_like_file_record(item)
    ]


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
    images = preview.get("_aImages") if isinstance(preview, dict) else []
    if not isinstance(images, list):
        return ""
    for item in images:
        if not isinstance(item, dict):
            continue
        base_url = str(item.get("_sBaseUrl") or "").strip()
        if not base_url:
            continue
        for field in ("_sFile530", "_sFile220", "_sFile100", "_sFile"):
            filename = str(item.get(field) or "").strip()
            if not filename:
                continue
            url = urllib.parse.urljoin(
                base_url.rstrip("/") + "/",
                filename.lstrip("/"),
            )
            parsed = urllib.parse.urlparse(url)
            hostname = (parsed.hostname or "").casefold()
            if (
                parsed.scheme.casefold() == "https"
                and hostname
                and (
                    hostname == "gamebanana.com"
                    or hostname.endswith(".gamebanana.com")
                )
            ):
                return url
    return ""

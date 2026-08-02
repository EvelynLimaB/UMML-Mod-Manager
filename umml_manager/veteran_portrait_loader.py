from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .veteran_local_portraits import LocalPortraitCache
from .veteran_media import VeteranMediaCache, VeteranMediaResult


@dataclass(frozen=True)
class PortraitLoadResult:
    """Result of resolving one costume portrait through the configured providers."""

    card_id: str
    portrait: Path | None
    source: str
    cache_hit: bool = False
    warning: str = ""


class VeteranPortraitResolver:
    """Resolve roster artwork without exposing provider details to the Tk layer.

    The installed game is authoritative and attempted first. The remote cache is
    only a cosmetic fallback. Both providers write exclusively to the Manager's
    own cache directory.
    """

    def __init__(
        self,
        local_cache: LocalPortraitCache,
        remote_cache: VeteranMediaCache,
    ):
        self.local_cache = local_cache
        self.remote_cache = remote_cache

    def cached(self, card_id: object) -> Path | None:
        local = self.local_cache.cached(card_id)
        if local is not None:
            return local
        return self.remote_cache.cached_selection(card_id, ()).portrait

    def resolve(self, card_id: object) -> PortraitLoadResult:
        text_id = str(card_id).strip()
        cached = self.cached(text_id)
        if cached is not None:
            return PortraitLoadResult(
                card_id=text_id,
                portrait=cached,
                source="cache",
                cache_hit=True,
            )

        local = self.local_cache.extract(text_id)
        if local.portrait is not None:
            return PortraitLoadResult(
                card_id=text_id,
                portrait=local.portrait,
                source="local",
                cache_hit=local.cache_hit,
                warning=local.warning,
            )

        remote = self.remote_cache.fetch_selection(text_id, ())
        if remote.portrait is not None:
            return PortraitLoadResult(
                card_id=text_id,
                portrait=remote.portrait,
                source="remote",
                cache_hit=bool(remote.cache_hits),
                warning=" ".join(remote.warnings),
            )

        warnings = [local.warning, *remote.warnings]
        return PortraitLoadResult(
            card_id=text_id,
            portrait=None,
            source="unavailable",
            warning=" ".join(item for item in warnings if item).strip(),
        )

    def resolve_skill_icons(self, skill_ids: Iterable[object]) -> VeteranMediaResult:
        """Resolve only skill icons, avoiding a redundant remote portrait request."""

        return self.remote_cache.fetch_selection(0, skill_ids)

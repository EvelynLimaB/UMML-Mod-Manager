from __future__ import annotations

import hashlib
import io
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

from .network import create_ssl_context, format_network_error


CHARACTER_IMAGE_BASE = "https://gametora.com/images/umamusume/characters"
SKILL_IMAGE_BASE = "https://media.gametora.com/umamusume/skills/icon"
ALLOWED_MEDIA_HOSTS = frozenset(
    {
        "gametora.com",
        "www.gametora.com",
        "media.gametora.com",
    }
)
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_SKILL_ICONS = 12


class VeteranMediaError(RuntimeError):
    """Raised when optional roster artwork cannot be fetched safely."""


@dataclass(frozen=True)
class VeteranMediaResult:
    portrait: Path | None
    skill_icons: tuple[tuple[int, Path], ...]
    cache_hits: int
    downloads: int
    warnings: tuple[str, ...] = ()


def character_image_url(card_id: object) -> str | None:
    resolved = _positive_integer(card_id)
    if resolved is None:
        return None
    character_id = resolved // 100
    if character_id <= 0:
        return None
    return (
        f"{CHARACTER_IMAGE_BASE}/"
        f"chara_stand_{character_id}_{resolved}.png"
    )


def skill_image_url(skill_id: object) -> str | None:
    resolved = _positive_integer(skill_id)
    if resolved is None:
        return None
    return f"{SKILL_IMAGE_BASE}/{resolved}.png"


def is_allowed_media_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url))
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").casefold() in ALLOWED_MEDIA_HOSTS
        and not parsed.username
        and not parsed.password
        and parsed.port in (None, 443)
    )


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        resolved = urllib.parse.urljoin(request.full_url, newurl)
        if not is_allowed_media_url(resolved):
            raise VeteranMediaError(
                "Roster media redirect left the approved GameTora image hosts."
            )
        return super().redirect_request(
            request,
            fp,
            code,
            message,
            headers,
            resolved,
        )


class VeteranMediaCache:
    """Optional, bounded cache for costume artwork and skill icons.

    Images are never bundled with the Manager and are fetched only after an
    explicit user action. Every URL is generated from a numeric game ID, HTTPS
    verified, host-restricted, size-limited, decoded by Pillow, and rewritten as
    a Manager-owned PNG before it reaches Tk.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        opener: Any | None = None,
    ):
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self._tls_configuration = None
        if opener is None:
            context, configuration = create_ssl_context()
            self._tls_configuration = configuration
            opener = urllib.request.build_opener(
                _SafeRedirectHandler(),
                urllib.request.HTTPSHandler(context=context),
            )
        self.opener = opener

    def fetch_selection(
        self,
        card_id: object,
        skill_ids: Iterable[object],
    ) -> VeteranMediaResult:
        portrait: Path | None = None
        icons: list[tuple[int, Path]] = []
        warnings: list[str] = []
        cache_hits = 0
        downloads = 0

        portrait_url = character_image_url(card_id)
        if portrait_url:
            try:
                portrait, cached = self._fetch_png(portrait_url, "portrait")
                cache_hits += int(cached)
                downloads += int(not cached)
            except VeteranMediaError as exc:
                warnings.append(f"Portrait: {exc}")

        seen: set[int] = set()
        for raw_id in skill_ids:
            skill_id = _positive_integer(raw_id)
            if skill_id is None or skill_id in seen:
                continue
            seen.add(skill_id)
            if len(icons) >= MAX_SKILL_ICONS:
                break
            url = skill_image_url(skill_id)
            if not url:
                continue
            try:
                path, cached = self._fetch_png(url, "skill")
            except VeteranMediaError as exc:
                warnings.append(f"Skill {skill_id}: {exc}")
                continue
            icons.append((skill_id, path))
            cache_hits += int(cached)
            downloads += int(not cached)

        return VeteranMediaResult(
            portrait=portrait,
            skill_icons=tuple(icons),
            cache_hits=cache_hits,
            downloads=downloads,
            warnings=tuple(warnings),
        )

    def cached_selection(
        self,
        card_id: object,
        skill_ids: Iterable[object],
    ) -> VeteranMediaResult:
        portrait: Path | None = None
        icons: list[tuple[int, Path]] = []
        portrait_url = character_image_url(card_id)
        if portrait_url:
            candidate = self._cache_path(portrait_url, "portrait")
            if candidate.is_file():
                portrait = candidate

        seen: set[int] = set()
        for raw_id in skill_ids:
            skill_id = _positive_integer(raw_id)
            if skill_id is None or skill_id in seen:
                continue
            seen.add(skill_id)
            if len(icons) >= MAX_SKILL_ICONS:
                break
            url = skill_image_url(skill_id)
            if not url:
                continue
            candidate = self._cache_path(url, "skill")
            if candidate.is_file():
                icons.append((skill_id, candidate))
        return VeteranMediaResult(
            portrait=portrait,
            skill_icons=tuple(icons),
            cache_hits=int(portrait is not None) + len(icons),
            downloads=0,
        )

    def clear(self) -> int:
        removed = 0
        for path in self.root.glob("*.png"):
            try:
                if path.is_file():
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    def _fetch_png(self, url: str, kind: str) -> tuple[Path, bool]:
        if not is_allowed_media_url(url):
            raise VeteranMediaError("Generated media URL is not approved.")
        target = self._cache_path(url, kind)
        if target.is_file():
            return target, True

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Uma-Mod-Manager/0.2 roster-media",
                "Accept": "image/png,image/webp,image/jpeg;q=0.8,*/*;q=0.1",
            },
            method="GET",
        )
        try:
            response = self.opener.open(request, timeout=20)
            with response:
                final_url = str(response.geturl() or url)
                if not is_allowed_media_url(final_url):
                    raise VeteranMediaError(
                        "Roster media response came from an unapproved host."
                    )
                content_type = str(
                    response.headers.get("Content-Type") or ""
                ).partition(";")[0].strip().casefold()
                if not content_type.startswith("image/"):
                    raise VeteranMediaError(
                        f"Server returned {content_type or 'an unknown type'}, not an image."
                    )
                declared = _positive_integer(
                    response.headers.get("Content-Length")
                )
                if declared is not None and declared > MAX_IMAGE_BYTES:
                    raise VeteranMediaError(
                        f"Image declares {declared:,} bytes; limit is {MAX_IMAGE_BYTES:,}."
                    )
                data = response.read(MAX_IMAGE_BYTES + 1)
        except VeteranMediaError:
            raise
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise VeteranMediaError(
                format_network_error(
                    "GameTora roster media",
                    exc,
                    self._tls_configuration,
                )
            ) from exc

        if len(data) > MAX_IMAGE_BYTES:
            raise VeteranMediaError(
                f"Image exceeded the {MAX_IMAGE_BYTES:,}-byte download limit."
            )
        if not data:
            raise VeteranMediaError("Server returned an empty image.")

        try:
            with Image.open(io.BytesIO(data)) as opened:
                width, height = opened.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise VeteranMediaError(
                        f"Image dimensions {width}×{height} exceed the safe pixel limit."
                    )
                image = opened.convert("RGBA")
                if kind == "portrait":
                    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                else:
                    image.thumbnail((128, 128), Image.Resampling.LANCZOS)
                self._atomic_save(image, target)
        except VeteranMediaError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise VeteranMediaError(f"Downloaded image could not be decoded: {exc}") from exc
        return target, False

    def _cache_path(self, url: str, kind: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        prefix = "portrait" if kind == "portrait" else "skill"
        return self.root / f"{prefix}-{digest}.png"

    @staticmethod
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


def _positive_integer(value: object) -> int | None:
    try:
        integer = int(value)
    except (TypeError, ValueError):
        return None
    return integer if integer > 0 else None

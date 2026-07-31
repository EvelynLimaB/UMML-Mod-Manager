from __future__ import annotations

import io
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass
from typing import Any, Callable

from PIL import Image, UnidentifiedImageError

from .network import TLSConfiguration, create_ssl_context, format_network_error
from .store import StoreError

MAX_PREVIEW_BYTES = 12 * 1024 * 1024
MAX_PREVIEW_PIXELS = 40_000_000
DEFAULT_PREVIEW_SIZE = (400, 190)


class PreviewImageError(StoreError):
    """Raised when a remote preview cannot be fetched or decoded safely."""


@dataclass(frozen=True)
class PreviewImage:
    image: Image.Image
    source_url: str
    content_type: str
    byte_size: int


class GameBananaPreviewRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse a redirect before urllib sends a request outside GameBanana."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        _require_gamebanana_https(newurl, "Preview redirect URL")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PreviewImageLoader:
    """Fetch and decode one untrusted remote preview without touching game state."""

    USER_AGENT = (
        "UMML-Manager/0.2 "
        "(+https://github.com/EvelynLimaB/UMML-Linux)"
    )

    def __init__(self, opener: Callable[..., Any] | None = None):
        self._tls_configuration: TLSConfiguration | None = None
        if opener is None:
            context, configuration = create_ssl_context()
            verified_opener = urllib.request.build_opener(
                GameBananaPreviewRedirectHandler(),
                urllib.request.HTTPSHandler(context=context),
            )
            self._opener = verified_opener.open
            self._tls_configuration = configuration
        else:
            self._opener = opener

    def load(
        self,
        url: str,
        *,
        max_size: tuple[int, int] = DEFAULT_PREVIEW_SIZE,
    ) -> PreviewImage:
        _require_gamebanana_https(url, "Preview URL")
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "image/avif,image/webp,image/png,image/jpeg,image/gif,*/*;q=0.2",
            },
        )
        try:
            with self._opener(request, timeout=30) as response:
                final_url = _response_url(response, url)
                _require_gamebanana_https(final_url, "Final preview URL")
                content_type = _content_type(response)
                if content_type and not content_type.startswith("image/"):
                    raise PreviewImageError(
                        f"Preview response was not an image: {content_type}"
                    )
                declared = _content_length(response)
                if declared > MAX_PREVIEW_BYTES:
                    raise PreviewImageError(
                        "Preview image declares more than the 12 MiB safety limit"
                    )
                payload = response.read(MAX_PREVIEW_BYTES + 1)
                if len(payload) > MAX_PREVIEW_BYTES:
                    raise PreviewImageError(
                        "Preview image exceeded the 12 MiB safety limit"
                    )
                if not payload:
                    raise PreviewImageError("Preview response was empty")
        except Exception as exc:
            if isinstance(exc, PreviewImageError):
                raise
            raise PreviewImageError(
                format_network_error(
                    "GameBanana preview",
                    exc,
                    self._tls_configuration,
                )
            ) from exc

        image = decode_preview_image(payload, max_size=max_size)
        return PreviewImage(
            image=image,
            source_url=final_url,
            content_type=content_type,
            byte_size=len(payload),
        )


def decode_preview_image(
    payload: bytes,
    *,
    max_size: tuple[int, int] = DEFAULT_PREVIEW_SIZE,
) -> Image.Image:
    if not payload:
        raise PreviewImageError("Preview image data was empty")
    width_limit, height_limit = max_size
    if width_limit <= 0 or height_limit <= 0:
        raise PreviewImageError("Preview display size must be positive")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(payload)) as source:
                width, height = source.size
                if width <= 0 or height <= 0:
                    raise PreviewImageError("Preview image has invalid dimensions")
                if width * height > MAX_PREVIEW_PIXELS:
                    raise PreviewImageError(
                        "Preview image exceeds the 40 megapixel safety limit"
                    )
                source.seek(0)
                image = source.convert("RGBA")
                image.thumbnail(
                    (width_limit, height_limit),
                    Image.Resampling.LANCZOS,
                    reducing_gap=3.0,
                )
                return image.copy()
    except PreviewImageError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise PreviewImageError(f"Preview image could not be decoded: {exc}") from exc


def _require_gamebanana_https(value: str, label: str) -> None:
    parsed = urllib.parse.urlparse(str(value))
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.scheme.casefold() != "https"
        or not hostname
        or not (
            hostname == "gamebanana.com"
            or hostname.endswith(".gamebanana.com")
        )
    ):
        raise PreviewImageError(
            f"{label} is not a verified GameBanana HTTPS URL: {value}"
        )


def _response_url(response: Any, fallback: str) -> str:
    getter = getattr(response, "geturl", None)
    return str(getter()) if callable(getter) else fallback


def _content_length(response: Any) -> int:
    headers = getattr(response, "headers", {})
    try:
        return max(0, int(headers.get("Content-Length", "0") or 0))
    except (TypeError, ValueError):
        return 0


def _content_type(response: Any) -> str:
    headers = getattr(response, "headers", {})
    getter = getattr(headers, "get_content_type", None)
    if callable(getter):
        return str(getter() or "").casefold()
    value = str(headers.get("Content-Type", "") or "")
    return value.split(";", 1)[0].strip().casefold()

from __future__ import annotations

import html
import http.cookiejar
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SYSTEM_CA_FILES = (
    # Fedora, Bazzite, RHEL, and other p11-kit based distributions.
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    # Debian, Ubuntu, Mint, and derivatives.
    "/etc/ssl/certs/ca-certificates.crt",
    # Common Alpine, SUSE, and BSD-style locations.
    "/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-bundle.crt",
    "/etc/ssl/ca-bundle.pem",
)

_GAMEBANANA_DOWNLOAD_REFERER = "https://gamebanana.com/"
_GAMEBANANA_DOWNLOAD_ACCEPT = (
    "application/octet-stream, application/zip, "
    "application/x-zip-compressed, application/x-tar, application/gzip, */*;q=0.1"
)
_GAMEBANANA_DENIAL_CONTENT_TYPES = {
    "application/json",
    "application/problem+json",
    "text/html",
    "text/json",
    "text/plain",
}
_GAMEBANANA_LANDING_MAX_BYTES = 1024 * 1024
_GAMEBANANA_LANDING_MAX_HOPS = 3
_GAMEBANANA_ARCHIVE_SUFFIXES = (
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".gz",
    ".xz",
)


class TLSConfigurationError(RuntimeError):
    """Raised when no safe certificate trust store can be configured."""


@dataclass(frozen=True)
class TLSConfiguration:
    cafile: str | None
    capath: str | None
    source: str

    def summary(self) -> str:
        parts = [f"Trust source: {self.source}"]
        if self.cafile:
            parts.append(f"CA file: {self.cafile}")
        if self.capath:
            parts.append(f"CA directory: {self.capath}")
        return "\n".join(parts)


class ProviderDownloadPolicy(urllib.request.BaseHandler):
    """Apply narrow provider context and resolve safe download landing pages.

    GameBanana's public API can return `/dl/<id>` or manager-oriented
    `/mmdl/<id>` links. Depending on its current anti-abuse and CDN routing,
    those links may redirect normally or return a small HTML page whose script,
    meta refresh, or download anchor points at the actual GameBanana file host.

    This handler keeps the provider cookie jar in memory, adds only the headers
    needed by those routes, and follows at most a few HTTPS links that remain on
    GameBanana-owned hosts. It never executes JavaScript, accepts HTTP, or follows
    an arbitrary third-party URL discovered in the page.
    """

    @staticmethod
    def _is_gamebanana_host(value: str) -> bool:
        parsed = urllib.parse.urlparse(value)
        hostname = (parsed.hostname or "").casefold()
        try:
            port = parsed.port
        except ValueError:
            return False
        return bool(
            parsed.scheme.casefold() == "https"
            and hostname
            and (hostname == "gamebanana.com" or hostname.endswith(".gamebanana.com"))
            and not parsed.username
            and not parsed.password
            and port in (None, 443)
        )

    @classmethod
    def _is_gamebanana_download(cls, request: urllib.request.Request) -> bool:
        parsed = urllib.parse.urlparse(request.full_url)
        path = parsed.path.casefold()
        return bool(
            cls._is_gamebanana_host(request.full_url)
            and (
                path.startswith("/dl/")
                or path.startswith("/download/")
                or path.startswith("/mmdl/")
            )
        )

    @staticmethod
    def _has_gamebanana_download_context(
        request: urllib.request.Request,
    ) -> bool:
        referer = str(request.get_header("Referer") or "").strip()
        return ProviderDownloadPolicy._is_gamebanana_host(referer)

    def https_request(
        self,
        request: urllib.request.Request,
    ) -> urllib.request.Request:
        if not self._is_gamebanana_download(request):
            return request
        if not request.has_header("Referer"):
            # Use a normal header rather than an unredirected header so urllib's
            # HTTPS redirect request retains the site context on the file CDN.
            request.add_header("Referer", _GAMEBANANA_DOWNLOAD_REFERER)
        if not request.has_header("Accept"):
            request.add_header("Accept", _GAMEBANANA_DOWNLOAD_ACCEPT)
        return request

    def https_response(self, request, response):
        if not self._has_gamebanana_download_context(request):
            return response
        raw_content_type = str(
            getattr(response, "headers", {}).get("Content-Type", "") or ""
        )
        content_type = raw_content_type.split(";", 1)[0].strip().casefold()
        if content_type not in _GAMEBANANA_DENIAL_CONTENT_TYPES:
            return response

        final_url = _response_url(response, request.full_url)
        body = b""
        if content_type == "text/html":
            body = response.read(_GAMEBANANA_LANDING_MAX_BYTES + 1)
        response.close()

        if len(body) > _GAMEBANANA_LANDING_MAX_BYTES:
            raise urllib.error.URLError(
                "GameBanana returned an oversized HTML download page instead "
                "of the selected mod file"
            )

        hops = int(getattr(request, "_umml_gamebanana_landing_hops", 0) or 0)
        target = (
            _extract_gamebanana_landing_target(body, final_url)
            if body and hops < _GAMEBANANA_LANDING_MAX_HOPS
            else ""
        )
        if not target and hops < _GAMEBANANA_LANDING_MAX_HOPS:
            # `/mmdl/<file-id>` is GameBanana's manager-oriented route. Some
            # `/dl/` responses return a browser landing or anti-abuse page even
            # though the same file remains available to an integrated manager.
            target = _gamebanana_manager_fallback(final_url)
        if target:
            next_request = urllib.request.Request(
                target,
                headers={
                    "User-Agent": str(
                        request.get_header("User-agent")
                        or request.get_header("User-Agent")
                        or "Uma-Mod-Manager/0.2"
                    ),
                    "Referer": final_url,
                    "Accept": _GAMEBANANA_DOWNLOAD_ACCEPT,
                },
            )
            setattr(
                next_request,
                "_umml_gamebanana_landing_hops",
                hops + 1,
            )
            return self.parent.open(next_request, timeout=60)

        title = _html_title(body)
        detail = f" Page title: {title}." if title else ""
        raise urllib.error.URLError(
            "GameBanana returned a web or error document instead of the "
            f"selected mod file (Content-Type: {content_type or 'unknown'}; "
            f"URL: {final_url}).{detail} No safe GameBanana CDN link was "
            "present in the response."
        )


def _response_url(response, fallback: str) -> str:
    getter = getattr(response, "geturl", None)
    try:
        value = str(getter()) if callable(getter) else ""
    except Exception:
        value = ""
    return value or fallback


def _gamebanana_manager_fallback(value: str) -> str:
    if not ProviderDownloadPolicy._is_gamebanana_host(value):
        return ""
    parsed = urllib.parse.urlparse(value)
    match = re.fullmatch(
        r"/(?:dl|download)/(\d+)(?:/.*)?",
        parsed.path,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return urllib.parse.urlunparse(
        (
            "https",
            "gamebanana.com",
            f"/mmdl/{match.group(1)}",
            "",
            "",
            "",
        )
    )


def _extract_gamebanana_landing_target(payload: bytes, base_url: str) -> str:
    """Return the best safe GameBanana file target exposed by a landing page."""

    try:
        text = payload.decode("utf-8", errors="replace")
    except Exception:
        return ""
    text = html.unescape(text).replace("\\/", "/")
    text = re.sub(
        r"\\u(?:002f|002F)",
        "/",
        text,
    )

    candidates: list[str] = []
    patterns = (
        r"(?is)<meta\b[^>]*\bcontent\s*=\s*[\"']([^\"']*?\burl\s*=\s*[^\"']+)[\"']",
        r"(?is)\b(?:window\.)?location(?:\.href)?\s*=\s*[\"']([^\"']+)[\"']",
        r"(?is)\blocation\.replace\(\s*[\"']([^\"']+)[\"']\s*\)",
        r"(?is)\b(?:href|data-url|data-download-url)\s*=\s*[\"']([^\"']+)[\"']",
        r"(?i)https://[^\s\"'<>]+",
    )
    for index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text):
            value = match.group(1) if index < 4 else match.group(0)
            if index == 0:
                refresh = re.search(r"(?is)\burl\s*=\s*(.+)$", value)
                value = refresh.group(1).strip() if refresh else ""
            value = value.strip().strip("\"' ")
            if value:
                candidates.append(value)

    ranked: list[tuple[int, str]] = []
    for raw in dict.fromkeys(candidates):
        candidate = urllib.parse.urljoin(base_url, raw)
        if not ProviderDownloadPolicy._is_gamebanana_host(candidate):
            continue
        parsed = urllib.parse.urlparse(candidate)
        path = parsed.path.casefold()
        if candidate == base_url:
            continue
        score = 0
        hostname = (parsed.hostname or "").casefold()
        if hostname == "files.gamebanana.com" or hostname.startswith("filecache"):
            score += 100
        if path.endswith(_GAMEBANANA_ARCHIVE_SUFFIXES):
            score += 80
        if (
            path.startswith("/dl/")
            or path.startswith("/download/")
            or path.startswith("/mmdl/")
        ):
            score += 30
        if "download" in parsed.query.casefold():
            score += 10
        if score:
            ranked.append((score, candidate))

    return max(ranked, default=(0, ""))[1]


def _html_title(payload: bytes) -> str:
    if not payload:
        return ""
    text = payload.decode("utf-8", errors="replace")
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    if not match:
        return ""
    value = re.sub(r"\s+", " ", html.unescape(match.group(1))).strip()
    return value[:120]


def resolve_tls_configuration(
    environ: Mapping[str, str] | None = None,
) -> TLSConfiguration:
    """Resolve an explicit, system, or bundled CA trust source.

    Frozen Python builds can retain OpenSSL paths from the build distribution.
    Those paths may not exist on Fedora-family targets such as Bazzite. Resolve
    the target system's trust store before falling back to certifi.
    """

    environment = os.environ if environ is None else environ
    env_file = environment.get("SSL_CERT_FILE", "").strip()
    env_dir = environment.get("SSL_CERT_DIR", "").strip()
    if env_file or env_dir:
        cafile = _required_file(env_file, "SSL_CERT_FILE") if env_file else None
        capath = _required_directory(env_dir, "SSL_CERT_DIR") if env_dir else None
        return TLSConfiguration(cafile, capath, "environment")

    defaults = ssl.get_default_verify_paths()
    default_file = _existing_file(defaults.cafile)
    default_dir = _existing_directory(defaults.capath)
    if default_file or default_dir:
        return TLSConfiguration(default_file, default_dir, "OpenSSL system defaults")

    for candidate in SYSTEM_CA_FILES:
        resolved = _existing_file(candidate)
        if resolved:
            return TLSConfiguration(resolved, None, "system trust store")

    try:
        import certifi

        bundled = _existing_file(certifi.where())
    except (ImportError, OSError):
        bundled = None
    if bundled:
        return TLSConfiguration(bundled, None, "bundled certifi")

    raise TLSConfigurationError(
        "No usable certificate authority bundle was found. Install the system "
        "ca-certificates package or set SSL_CERT_FILE to a trusted PEM bundle. "
        "Certificate verification was not disabled."
    )


def create_ssl_context() -> tuple[ssl.SSLContext, TLSConfiguration]:
    configuration = resolve_tls_configuration()
    try:
        context = ssl.create_default_context(
            cafile=configuration.cafile,
            capath=configuration.capath,
        )
    except (OSError, ssl.SSLError) as exc:
        raise TLSConfigurationError(
            "The selected certificate trust store could not be loaded.\n"
            f"{configuration.summary()}\n"
            f"Reason: {exc}"
        ) from exc
    return context, configuration


def build_https_opener() -> tuple[urllib.request.OpenerDirector, TLSConfiguration]:
    context, configuration = create_ssl_context()
    # Keep cookies in memory for the lifetime of one client. GameBanana can set
    # session or anti-abuse cookies while returning API metadata and then expect
    # them on the subsequent download request. The jar is deliberately not
    # persisted, so provider state never escapes the running Manager process.
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        ProviderDownloadPolicy(),
        urllib.request.HTTPSHandler(context=context),
        urllib.request.HTTPCookieProcessor(cookie_jar),
    )
    return opener, configuration


def format_network_error(
    service: str,
    exc: BaseException,
    configuration: TLSConfiguration | None,
) -> str:
    if _contains_certificate_error(exc):
        trust = configuration.summary() if configuration else "Trust source: custom opener"
        return (
            f"{service} TLS certificate verification failed.\n"
            f"{trust}\n"
            "Run UMML diagnostics to inspect the certificate trust source. "
            "Do not disable certificate verification.\n"
            f"Original error: {exc}"
        )
    return f"{service} request failed: {exc}"


def tls_diagnostics() -> tuple[str, bool]:
    try:
        configuration = resolve_tls_configuration()
        # Loading the context catches malformed or unreadable bundles without
        # making a network request from diagnostics.
        ssl.create_default_context(
            cafile=configuration.cafile,
            capath=configuration.capath,
        )
    except Exception as exc:
        return (
            "HTTPS certificate verification: NOT READY\n"
            f"{exc}\n"
            "Certificate verification remains enabled.",
            False,
        )
    return (
        "HTTPS certificate verification: READY\n" + configuration.summary(),
        True,
    )


def _contains_certificate_error(exc: BaseException) -> bool:
    pending: list[BaseException] = [exc]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in visited:
            continue
        visited.add(identity)
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        if isinstance(current, urllib.error.URLError) and isinstance(
            current.reason, BaseException
        ):
            pending.append(current.reason)
        for nested in (current.__cause__, current.__context__):
            if isinstance(nested, BaseException):
                pending.append(nested)
    return False


def _required_file(value: str, variable: str) -> str:
    resolved = _existing_file(value)
    if not resolved:
        raise TLSConfigurationError(
            f"{variable} points to a missing or unreadable file: {value}"
        )
    return resolved


def _required_directory(value: str, variable: str) -> str:
    resolved = _existing_directory(value)
    if not resolved:
        raise TLSConfigurationError(
            f"{variable} points to a missing or unreadable directory: {value}"
        )
    return resolved


def _existing_file(value: str | os.PathLike[str] | None) -> str | None:
    if not value:
        return None
    path = Path(value).expanduser()
    try:
        return str(path.resolve()) if path.is_file() else None
    except OSError:
        return None


def _existing_directory(value: str | os.PathLike[str] | None) -> str | None:
    if not value:
        return None
    path = Path(value).expanduser()
    try:
        return str(path.resolve()) if path.is_dir() else None
    except OSError:
        return None

from __future__ import annotations

import http.cookiejar
import os
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
    """Apply narrow provider headers and reject obvious web error payloads.

    GameBanana's public API can return `/dl/<id>` or manager-oriented
    `/mmdl/<id>` links whose redirect paths are protected by normal session and
    anti-abuse behavior. Treat those requests as site-originated downloads
    rather than context-free scraper requests. The policy deliberately applies
    only to GameBanana download routes and never weakens TLS or accepts HTTP.
    """

    @staticmethod
    def _is_gamebanana_download(request: urllib.request.Request) -> bool:
        parsed = urllib.parse.urlparse(request.full_url)
        hostname = (parsed.hostname or "").casefold()
        path = parsed.path.casefold()
        return bool(
            parsed.scheme.casefold() == "https"
            and (
                hostname == "gamebanana.com"
                or hostname.endswith(".gamebanana.com")
            )
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
        return referer.startswith(_GAMEBANANA_DOWNLOAD_REFERER)

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
        try:
            response.close()
        finally:
            raise urllib.error.URLError(
                "GameBanana returned a web or error document instead of the "
                f"selected mod file (Content-Type: {content_type or 'unknown'})"
            )


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

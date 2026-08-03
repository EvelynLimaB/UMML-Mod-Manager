from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from .legacy_archive import import_loose_legacy_archive
from .library import ManagerStore, UnrecognizedModError
from .models import SourceSpec
from .providers.gamebanana import GameBananaFile, GameBananaMod
from .providers.gamebanana_previews import PreviewGameBananaClient
from .regions import region_from_game_name
from .safety import hash_file
from .store import StoreError

_BROWSER_WAIT_SECONDS = 10 * 60
_BROWSER_POLL_SECONDS = 0.75
_PARTIAL_SUFFIXES = (
    ".crdownload",
    ".download",
    ".part",
    ".partial",
    ".tmp",
)
_ARCHIVE_SUFFIXES = (
    ".zip",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".gz",
)
_ORIGINAL_IMPORT_MOD = PreviewGameBananaClient.import_mod


@dataclass(frozen=True)
class BrowserFileExpectation:
    """Identity information used to recognize the browser download safely."""

    file_id: int
    name: str
    size_bytes: int = 0
    md5: str = ""


@dataclass(frozen=True)
class _ObservedFile:
    size: int
    modified_ns: int


def _requires_browser_download(error: BaseException) -> bool:
    """Return true only for GameBanana's HTML-instead-of-file response."""

    pending: list[BaseException] = [error]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in visited:
            continue
        visited.add(identity)
        text = str(current).casefold()
        if (
            "gamebanana" in text
            and "text/html" in text
            and (
                "web or error document" in text
                or "no safe gamebanana cdn link" in text
            )
        ):
            return True
        for nested in (current.__cause__, current.__context__):
            if isinstance(nested, BaseException):
                pending.append(nested)
        reason = getattr(current, "reason", None)
        if isinstance(reason, BaseException):
            pending.append(reason)
    return False


def _selected_file(mod: GameBananaMod, file_id: int | None) -> GameBananaFile:
    if not mod.files:
        raise StoreError("GameBanana submission has no downloadable files")
    selected = (
        next((item for item in mod.files if item.id == file_id), None)
        if file_id
        else max(mod.files, key=lambda item: (item.date_added, item.id))
    )
    if selected is None:
        raise StoreError(f"GameBanana file not found: {file_id}")
    return selected


def _fetch_expectation(
    client: PreviewGameBananaClient,
    selected: GameBananaFile,
) -> BrowserFileExpectation:
    """Fetch stable file identity without depending on the download route."""

    name = selected.name
    size = 0
    md5 = ""
    try:
        value = client._request_json(
            f"https://gamebanana.com/apiv11/File/{selected.id}",
            {
                "_csvProperties": (
                    "_idRow,_sFile,_nFilesize,_sMd5Checksum"
                )
            },
        )
    except StoreError:
        value = None
    if isinstance(value, dict):
        name = str(value.get("_sFile") or name)
        try:
            size = max(0, int(value.get("_nFilesize") or 0))
        except (TypeError, ValueError):
            size = 0
        candidate_md5 = str(value.get("_sMd5Checksum") or "").strip().casefold()
        if re.fullmatch(r"[0-9a-f]{32}", candidate_md5):
            md5 = candidate_md5
    return BrowserFileExpectation(selected.id, name, size, md5)


def _xdg_download_directory() -> Path | None:
    configured = os.environ.get("XDG_DOWNLOAD_DIR", "").strip()
    if configured:
        return Path(os.path.expandvars(configured.strip('"'))).expanduser()
    config = Path.home() / ".config" / "user-dirs.dirs"
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^XDG_DOWNLOAD_DIR="([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        return None
    value = match.group(1).replace("$HOME", str(Path.home()))
    return Path(os.path.expandvars(value)).expanduser()


def browser_download_directories() -> tuple[Path, ...]:
    """Return existing, user-owned locations browsers normally download to."""

    values: list[Path] = []
    override = os.environ.get("UMML_GAMEBANANA_DOWNLOAD_DIR", "").strip()
    if override:
        values.append(Path(override).expanduser())
    xdg = _xdg_download_directory()
    if xdg is not None:
        values.append(xdg)
    values.append(Path.home() / "Downloads")

    result: list[Path] = []
    seen: set[str] = set()
    for value in values:
        try:
            resolved = value.resolve(strict=False)
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if resolved.is_dir() and not resolved.is_symlink():
            result.append(resolved)
    return tuple(result)


def _snapshot(directories: Iterable[Path]) -> dict[Path, _ObservedFile]:
    result: dict[Path, _ObservedFile] = {}
    for directory in directories:
        try:
            entries = tuple(directory.iterdir())
        except OSError:
            continue
        for path in entries:
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                stat = path.stat()
            except OSError:
                continue
            result[path] = _ObservedFile(stat.st_size, stat.st_mtime_ns)
    return result


def _archive_name_matches(path: Path, expected: BrowserFileExpectation) -> bool:
    lower = path.name.casefold()
    if lower.endswith(_PARTIAL_SUFFIXES):
        return False
    if not lower.endswith(_ARCHIVE_SUFFIXES):
        return False
    expected_name = Path(expected.name).name.casefold()
    if lower == expected_name:
        return True
    expected_stem = re.sub(r"[^a-z0-9]+", "", Path(expected_name).stem)
    actual_stem = re.sub(r"[^a-z0-9]+", "", path.stem)
    return bool(expected_stem and actual_stem.startswith(expected_stem))


def _md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_is_complete(
    path: Path,
    expected: BrowserFileExpectation,
) -> bool:
    try:
        if path.is_symlink() or not path.is_file():
            return False
        size = path.stat().st_size
    except OSError:
        return False
    if size <= 0:
        return False
    if expected.size_bytes and size != expected.size_bytes:
        return False
    if expected.md5:
        try:
            return _md5_file(path) == expected.md5
        except OSError:
            return False
    return True


def wait_for_browser_download(
    url: str,
    expected: BrowserFileExpectation,
    *,
    timeout: float = _BROWSER_WAIT_SECONDS,
    poll: float = _BROWSER_POLL_SECONDS,
    opener: Callable[[str], bool] = webbrowser.open,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Path:
    """Open GameBanana in the real browser and adopt its completed archive."""

    parsed = urllib.parse.urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.scheme.casefold() != "https"
        or not hostname
        or not (hostname == "gamebanana.com" or hostname.endswith(".gamebanana.com"))
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise StoreError(f"Unsafe GameBanana browser URL: {url}")

    directories = browser_download_directories()
    if not directories:
        raise StoreError(
            "No usable browser Downloads directory was found. Open the mod page "
            "and import the archive from Local folders instead."
        )
    before = _snapshot(directories)
    if not opener(url):
        raise StoreError(
            "The default browser could not be opened for the GameBanana download."
        )

    deadline = clock() + max(1.0, timeout)
    stable: dict[Path, tuple[int, int]] = {}
    while clock() < deadline:
        current = _snapshot(directories)
        candidates: list[tuple[int, Path, _ObservedFile]] = []
        for path, observed in current.items():
            previous = before.get(path)
            if previous == observed:
                continue
            if not _archive_name_matches(path, expected):
                continue
            score = 0
            if expected.size_bytes and observed.size == expected.size_bytes:
                score += 100
            if path.name.casefold() == Path(expected.name).name.casefold():
                score += 50
            score += min(40, max(0, int(observed.modified_ns / 1_000_000_000)))
            candidates.append((score, path, observed))
        candidates.sort(key=lambda item: (item[0], item[2].modified_ns), reverse=True)
        for _score, path, observed in candidates:
            previous_stable = stable.get(path)
            count = previous_stable[1] + 1 if previous_stable and previous_stable[0] == observed.size else 1
            stable[path] = (observed.size, count)
            if count >= 2 and _candidate_is_complete(path, expected):
                return path
        sleeper(max(0.05, poll))

    searched = ", ".join(str(path) for path in directories)
    raise StoreError(
        "GameBanana requires a browser session for this file. The download page "
        f"was opened, but {expected.name} was not detected within "
        f"{int(timeout)} seconds. Download it in the browser, then import it "
        f"from Local folders. Watched: {searched}"
    )


def _import_browser_archive(
    store: ManagerStore,
    mod: GameBananaMod,
    selected: GameBananaFile,
    archive: Path,
):
    source = SourceSpec(
        provider="gamebanana",
        url=mod.profile_url,
        submission_id=mod.id,
        file_id=selected.id,
        updated_at=selected.date_added or mod.date_updated,
        file_name=archive.name,
        sha256=hash_file(archive),
        size_bytes=archive.stat().st_size,
        fetched_at=datetime.now(timezone.utc).isoformat(),
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


def _import_mod_with_browser_bridge(
    self: PreviewGameBananaClient,
    store: ManagerStore,
    value: str,
    *,
    file_id: int | None = None,
):
    try:
        return _ORIGINAL_IMPORT_MOD(self, store, value, file_id=file_id)
    except StoreError as error:
        if not _requires_browser_download(error):
            raise

    mod = self.fetch(value)
    selected = _selected_file(mod, file_id)
    expectation = _fetch_expectation(self, selected)
    archive = wait_for_browser_download(selected.url, expectation)
    return _import_browser_archive(store, mod, selected, archive)


def install_browser_bridge() -> None:
    """Install once without changing the public provider class identity."""

    if getattr(PreviewGameBananaClient, "_umml_browser_bridge", False):
        return
    PreviewGameBananaClient.import_mod = _import_mod_with_browser_bridge
    PreviewGameBananaClient._umml_browser_bridge = True


install_browser_bridge()

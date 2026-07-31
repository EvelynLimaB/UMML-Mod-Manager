from __future__ import annotations

import json
import os
import re
import tarfile
import zipfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

_METADATA = ("umml-mod.json", "setting.json", "setting.yml", "setting.yaml")
_ARCHIVES = (".zip", ".tar.gz", ".tgz", ".tar")
_SKIP_DIRS = {
    ".cache",
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    "steamapps",
    "compatdata",
    "shadercache",
    "venv",
    ".venv",
}
_METADATA_HINTS = {
    "id",
    "title",
    "author",
    "submitter",
    "version",
    "mod_version",
    "description",
    "region",
    "regions",
}
_ARCHIVE_NAME_HINT = re.compile(r"(?:uma|umml|hachimi|mod|skin|texture)", re.IGNORECASE)
_ROOT_SCAN_ENTRY_LIMIT = 20_000
_ROOT_SCAN_DEPTH_LIMIT = 64


@dataclass(frozen=True)
class ModCandidate:
    path: Path
    kind: str
    name: str
    confidence: str
    reason: str


def default_search_roots() -> list[Path]:
    home = Path.home()
    roots = [home / "Downloads", home / "Documents", home / "Desktop"]
    roots[:0] = _xdg_user_directories(home)
    result: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.expanduser().resolve()
        except OSError:
            resolved = root.expanduser()
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def is_mod_root(path: str | Path) -> bool:
    return describe_mod_root(path) is not None


def describe_mod_root(path: str | Path) -> ModCandidate | None:
    root = Path(path)
    metadata = _recognized_metadata(root)
    assets = (root / "assets").is_dir() and _has_any_regular_file(root / "assets")
    hachimi = (root / "hachimi").is_dir() and _has_any_regular_file(root / "hachimi")
    if not (assets or hachimi or metadata == "umml-mod.json"):
        return None
    if metadata and assets:
        confidence = "high"
        reason = f"{metadata} and assets/"
    elif metadata == "umml-mod.json":
        confidence = "high"
        reason = metadata
    elif assets:
        confidence = "medium"
        reason = "assets/ with regular mod files"
    else:
        confidence = "medium"
        reason = "hachimi/ runtime content"
    return ModCandidate(root, "folder", root.name, confidence, reason)


def scan_mod_candidates(
    roots: Iterable[str | Path],
    *,
    max_depth: int = 5,
    max_entries: int = 20_000,
    include_archives: bool = True,
) -> list[ModCandidate]:
    queue: deque[tuple[Path, int]] = deque()
    for value in roots:
        path = Path(value).expanduser()
        if path.is_dir():
            queue.append((path, 0))
    candidates: dict[Path, ModCandidate] = {}
    inspected = 0
    while queue and inspected < max_entries:
        current, depth = queue.popleft()
        inspected += 1
        candidate = describe_mod_root(current)
        if candidate:
            candidates[_resolve_or_original(current)] = candidate
            continue
        if depth >= max_depth:
            continue
        try:
            iterator = os.scandir(current)
        except OSError:
            continue
        with iterator:
            for entry in iterator:
                inspected += 1
                if inspected > max_entries:
                    break
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.casefold() in _SKIP_DIRS or entry.name.startswith("."):
                            continue
                        queue.append((Path(entry.path), depth + 1))
                    elif include_archives and entry.is_file(follow_symlinks=False):
                        child = Path(entry.path)
                        if _archive_suffix(child):
                            archive = describe_archive(child)
                            if archive:
                                candidates[_resolve_or_original(child)] = archive
                except OSError:
                    continue
    return sorted(
        candidates.values(),
        key=lambda item: (item.kind, item.name.casefold(), str(item.path)),
    )


def locate_mod_root(path: str | Path, *, max_depth: int = 5) -> Path:
    selected = Path(path).expanduser().resolve()
    if is_mod_root(selected):
        return selected
    candidates = scan_mod_candidates(
        [selected],
        max_depth=max_depth,
        include_archives=False,
    )
    if not candidates:
        raise ValueError(f"No UMML-compatible mod folder found under {selected}")
    candidates.sort(
        key=lambda item: (
            len(item.path.relative_to(selected).parts),
            item.confidence != "high",
            str(item.path),
        )
    )
    return candidates[0].path


def describe_archive(path: str | Path) -> ModCandidate | None:
    archive = Path(path)
    suffix = _archive_suffix(archive)
    if not suffix:
        return None
    reason = f"{suffix.lstrip('.').upper()} archive"
    confidence = "low"
    try:
        names = list(_archive_names(archive, limit=3000))
        if names:
            base_names = {_base_name(name).casefold() for name in names}
            has_manifest = "umml-mod.json" in base_names
            has_metadata = any(marker.casefold() in base_names for marker in _METADATA)
            has_assets = any(
                "/assets/" in f"/{name.casefold().strip('/')}/"
                for name in names
            )
            has_hachimi = any(
                "/hachimi/" in f"/{name.casefold().strip('/')}/"
                for name in names
            )
            if has_manifest and has_assets:
                confidence = "high"
                reason += " containing UMML manifest and assets"
            elif has_metadata and (has_assets or has_hachimi):
                confidence = "medium"
                reason += " containing metadata and mod content"
            elif has_assets or has_hachimi:
                confidence = "medium"
                reason += " containing mod content"
    except (OSError, tarfile.TarError, zipfile.BadZipFile):
        return None
    if confidence == "low" and not _ARCHIVE_NAME_HINT.search(archive.stem):
        return None
    if confidence == "low":
        reason += " with a mod-like filename; contents need manual verification"
    return ModCandidate(
        archive,
        "archive",
        _archive_stem(archive),
        confidence,
        reason,
    )


def _archive_names(archive: Path, *, limit: int) -> Iterator[str]:
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as package:
            for index, item in enumerate(package.infolist()):
                if index >= limit:
                    break
                yield item.filename.replace("\\", "/")
        return
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as package:
            for index, item in enumerate(package):
                if index >= limit:
                    break
                yield item.name.replace("\\", "/")


def _recognized_metadata(root: Path) -> str:
    manifest = root / "umml-mod.json"
    if manifest.is_file():
        return manifest.name
    for name in ("setting.json", "setting.yml", "setting.yaml"):
        path = root / name
        if not path.is_file():
            continue
        try:
            if path.suffix.casefold() == ".json":
                value = json.loads(path.read_text(encoding="utf-8"))
            else:
                import yaml

                value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and _METADATA_HINTS.intersection(
            str(key).casefold() for key in value
        ):
            return name
    return ""


def _archive_suffix(path: Path) -> str:
    lower = path.name.casefold()
    return next(
        (suffix for suffix in _ARCHIVES if lower.endswith(suffix)),
        "",
    )


def _archive_stem(path: Path) -> str:
    name = path.name
    suffix = _archive_suffix(path)
    return name[: -len(suffix)] if suffix else path.stem


def _base_name(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def _has_any_regular_file(root: Path) -> bool:
    """Return whether *root* contains a regular file without following links.

    Real legacy UMML packages often contain a wrapper plus deeply nested Unity
    asset paths. The previous four-level shortcut incorrectly rejected those
    packages after the compatibility normalizer had already validated them.
    Traversal remains bounded by entry and depth limits and never follows
    symbolic links.
    """

    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    inspected = 0
    while queue and inspected < _ROOT_SCAN_ENTRY_LIMIT:
        directory, depth = queue.popleft()
        try:
            iterator = os.scandir(directory)
        except (OSError, PermissionError):
            continue
        with iterator:
            for entry in iterator:
                inspected += 1
                if inspected > _ROOT_SCAN_ENTRY_LIMIT:
                    return False
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        return True
                    if (
                        depth < _ROOT_SCAN_DEPTH_LIMIT
                        and entry.is_dir(follow_symlinks=False)
                    ):
                        queue.append((Path(entry.path), depth + 1))
                except OSError:
                    continue
    return False


def _xdg_user_directories(home: Path) -> list[Path]:
    values: list[Path] = []
    environment = os.environ.get("XDG_DOWNLOAD_DIR", "").strip().strip('"')
    if environment:
        values.append(Path(os.path.expandvars(environment)).expanduser())
    config = (
        Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        / "user-dirs.dirs"
    )
    try:
        text = config.read_text(encoding="utf-8")
    except OSError:
        return values
    for key in ("DOWNLOAD", "DOCUMENTS", "DESKTOP"):
        match = re.search(
            rf'^XDG_{key}_DIR="([^"]+)"',
            text,
            flags=re.MULTILINE,
        )
        if match:
            raw = match.group(1).replace("$HOME", str(home))
            values.append(Path(os.path.expandvars(raw)).expanduser())
    return values


def _resolve_or_original(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path

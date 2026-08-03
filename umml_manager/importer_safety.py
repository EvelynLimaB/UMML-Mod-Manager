from __future__ import annotations

import stat
import unicodedata
from pathlib import Path


class ImportSafetyError(RuntimeError):
    """Raised when a user-selected import input is not a safe regular path."""


def resolve_regular_file(value: str | Path, *, label: str) -> Path:
    """Reject links and non-files before resolving the selected path."""

    selected = Path(value).expanduser()
    try:
        mode = selected.lstat().st_mode
    except OSError as exc:
        raise ImportSafetyError(f"{label} not found: {selected}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ImportSafetyError(
            f"{label} must be a regular non-symlink file: {selected}"
        )
    return selected.resolve()


def resolve_regular_directory(value: str | Path, *, label: str) -> Path:
    """Reject links and non-directories before resolving the selected path."""

    selected = Path(value).expanduser()
    try:
        mode = selected.lstat().st_mode
    except OSError as exc:
        raise ImportSafetyError(f"{label} not found: {selected}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ImportSafetyError(
            f"{label} must be a regular non-symlink directory: {selected}"
        )
    return selected.resolve()


def archive_collision_key(relative_path: str) -> str:
    """Return a cross-platform key for archive path collision checks."""

    return unicodedata.normalize("NFC", relative_path).casefold()


def latest_regular_json(directory: str | Path) -> Path | None:
    """Return the newest regular, non-symlink JSON file in a directory."""

    root = Path(directory)
    candidates: list[tuple[int, Path]] = []
    for path in root.glob("*.json"):
        try:
            metadata = path.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            continue
        candidates.append((metadata.st_mtime_ns, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]

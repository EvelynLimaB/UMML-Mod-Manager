from __future__ import annotations

import os
import stat
import unicodedata
from pathlib import Path


class ImportSafetyError(RuntimeError):
    """Raised when a user-selected import input is not a safe regular path."""


def is_link_like(path: str | Path, mode: int | None = None) -> bool:
    """Return whether *path* is a symlink or Windows directory junction.

    ``stat.S_ISLNK`` covers ordinary symbolic links. Windows can also expose
    directory junctions as reparse points that resolve like links without using
    the POSIX symlink mode, so importer boundaries reject both forms.
    """

    selected = Path(path)
    if mode is None:
        try:
            mode = selected.lstat().st_mode
        except OSError:
            return False
    if stat.S_ISLNK(mode):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is None:
        return False
    try:
        return bool(isjunction(selected))
    except OSError:
        return False


def resolve_regular_file(value: str | Path, *, label: str) -> Path:
    """Reject links and non-files before resolving the selected path."""

    selected = Path(value).expanduser()
    try:
        mode = selected.lstat().st_mode
    except OSError as exc:
        raise ImportSafetyError(f"{label} not found: {selected}") from exc
    if is_link_like(selected, mode) or not stat.S_ISREG(mode):
        raise ImportSafetyError(
            f"{label} must be a regular non-link file: {selected}"
        )
    return selected.resolve()


def resolve_regular_directory(value: str | Path, *, label: str) -> Path:
    """Reject links and non-directories before resolving the selected path."""

    selected = Path(value).expanduser()
    try:
        mode = selected.lstat().st_mode
    except OSError as exc:
        raise ImportSafetyError(f"{label} not found: {selected}") from exc
    if is_link_like(selected, mode) or not stat.S_ISDIR(mode):
        raise ImportSafetyError(
            f"{label} must be a regular non-link directory: {selected}"
        )
    return selected.resolve()


def archive_collision_key(relative_path: str) -> str:
    """Return a cross-platform key for archive path collision checks."""

    return unicodedata.normalize("NFC", relative_path).casefold()


def latest_regular_json(directory: str | Path) -> Path | None:
    """Return the newest regular, non-link JSON file in a directory."""

    root = Path(directory)
    candidates: list[tuple[int, Path]] = []
    for path in root.glob("*.json"):
        try:
            metadata = path.lstat()
        except OSError:
            continue
        if is_link_like(path, metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            continue
        candidates.append((metadata.st_mtime_ns, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]

from __future__ import annotations

import os
import stat
import unicodedata
from pathlib import Path
from typing import Any


class ImportSafetyError(RuntimeError):
    """Raised when a user-selected import input is not a safe regular path."""


def is_link_like(
    path: str | Path,
    metadata: os.stat_result | int | None = None,
) -> bool:
    """Return whether *path* is a symlink or Windows reparse-point link.

    POSIX links are represented in ``st_mode``. Windows directory junctions and
    some symbolic links are represented primarily through reparse metadata, so
    callers must preserve the complete ``lstat`` result instead of reducing it
    to the mode bits before this check.
    """

    selected = Path(path)
    if metadata is None:
        try:
            metadata = selected.lstat()
        except OSError:
            return False

    if isinstance(metadata, int):
        mode = metadata
        file_attributes = 0
        reparse_tag = 0
    else:
        mode = metadata.st_mode
        file_attributes = int(getattr(metadata, "st_file_attributes", 0) or 0)
        reparse_tag = int(getattr(metadata, "st_reparse_tag", 0) or 0)

    if stat.S_ISLNK(mode):
        return True

    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0) or 0)
    if reparse_tag or (reparse_flag and file_attributes & reparse_flag):
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
        metadata = selected.lstat()
    except OSError as exc:
        raise ImportSafetyError(f"{label} not found: {selected}") from exc
    if is_link_like(selected, metadata) or not stat.S_ISREG(metadata.st_mode):
        raise ImportSafetyError(
            f"{label} must be a regular non-link file: {selected}"
        )
    return selected.resolve()


def resolve_regular_directory(value: str | Path, *, label: str) -> Path:
    """Reject links and non-directories before resolving the selected path."""

    selected = Path(value).expanduser()
    try:
        metadata = selected.lstat()
    except OSError as exc:
        raise ImportSafetyError(f"{label} not found: {selected}") from exc
    if is_link_like(selected, metadata) or not stat.S_ISDIR(metadata.st_mode):
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
        if is_link_like(path, metadata) or not stat.S_ISREG(metadata.st_mode):
            continue
        candidates.append((metadata.st_mtime_ns, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]

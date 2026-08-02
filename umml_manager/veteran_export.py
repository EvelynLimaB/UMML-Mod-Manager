from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from .veterans import VeteranDataError


def atomic_export_json(destination: str | Path, payload: Any) -> Path:
    """Write a user-selected JSON export without following a target symlink."""

    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        if target.exists() or target.is_symlink():
            mode = target.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise VeteranDataError("Export destination cannot be a symlink")
            if not stat.S_ISREG(mode):
                raise VeteranDataError("Export destination must be a regular file")
    except OSError as exc:
        raise VeteranDataError(f"Could not validate export destination: {exc}") from exc

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        document = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n"
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return target

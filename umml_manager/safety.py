from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SHA256_LENGTH = 64
MAX_LOCAL_FILES = 100_000
MAX_LOCAL_BYTES = 32 * 1024 * 1024 * 1024


class SafetyError(RuntimeError):
    """Raised when an untrusted path or filesystem object is unsafe."""


def normalize_relative_path(value: str) -> str:
    """Return one canonical POSIX relative path or reject it.

    Mod manifests, prepared caches, and deployment state are all untrusted
    inputs. Normalizing at every boundary keeps a corrupted registry from
    turning ``Persistent/dat / relative`` into a write outside the game tree.
    """

    if not isinstance(value, str):
        raise SafetyError("Managed path must be text")
    if not value or "\x00" in value:
        raise SafetyError("Managed path is empty or contains a NUL byte")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts:
        raise SafetyError(f"Managed path must be relative: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise SafetyError(f"Managed path contains an unsafe segment: {value!r}")
    if ":" in path.parts[0]:
        raise SafetyError(f"Managed path contains a drive prefix: {value!r}")
    return path.as_posix()


def validate_sha256(value: str) -> str:
    text = str(value).casefold().strip()
    if len(text) != SHA256_LENGTH or any(char not in "0123456789abcdef" for char in text):
        raise SafetyError(f"Invalid SHA-256 digest: {value!r}")
    return text


def path_under(root: str | Path, relative: str) -> Path:
    """Resolve a safe target below *root* without following a leaf symlink."""

    root_path = Path(root).expanduser().resolve()
    canonical = normalize_relative_path(relative)
    candidate = root_path.joinpath(*PurePosixPath(canonical).parts)
    try:
        parent = candidate.parent.resolve(strict=False)
    except OSError as exc:
        raise SafetyError(f"Could not resolve managed path parent: {candidate}") from exc
    if not _is_relative_to(parent, root_path):
        raise SafetyError(f"Managed path escapes its root: {relative!r}")
    if candidate.is_symlink():
        raise SafetyError(f"Managed target is a symbolic link: {candidate}")
    return candidate


def validate_regular_tree(
    root: str | Path,
    *,
    max_files: int = MAX_LOCAL_FILES,
    max_bytes: int = MAX_LOCAL_BYTES,
    ignored_names: Iterable[str] = (),
) -> tuple[int, int]:
    """Reject symlinks and special files before importing a local tree."""

    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise SafetyError(f"Folder does not exist: {base}")
    ignored = set(ignored_names)
    files = 0
    total = 0
    stack = [base]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise SafetyError(f"Could not inspect folder: {directory}: {exc}") from exc
        for entry in entries:
            if entry.name in ignored:
                continue
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise SafetyError(f"Could not inspect filesystem entry: {entry.path}: {exc}") from exc
            if stat.S_ISLNK(mode):
                raise SafetyError(f"Symbolic links are not accepted in mod packages: {entry.path}")
            if stat.S_ISDIR(mode):
                stack.append(Path(entry.path))
                continue
            if not stat.S_ISREG(mode):
                raise SafetyError(f"Special filesystem entry is not accepted: {entry.path}")
            files += 1
            total += max(0, entry.stat(follow_symlinks=False).st_size)
            if files > max_files:
                raise SafetyError(
                    f"Folder contains more than {max_files:,} files and was rejected: {base}"
                )
            if total > max_bytes:
                gib = total / (1024 * 1024 * 1024)
                limit = max_bytes / (1024 * 1024 * 1024)
                raise SafetyError(
                    f"Folder contains {gib:.2f} GiB; the safety limit is {limit:.0f} GiB: {base}"
                )
    return files, total


def hash_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(root: str | Path) -> str:
    base = Path(root).expanduser().resolve()
    validate_regular_tree(base)
    digest = hashlib.sha256()
    files = sorted(path for path in base.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(base).as_posix()
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        digest.update(hash_file(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def atomic_copy_file(source: str | Path, target: str | Path) -> None:
    """Copy one regular file and atomically replace the target."""

    source_path = Path(source)
    target_path = Path(target)
    try:
        mode = source_path.lstat().st_mode
    except OSError as exc:
        raise SafetyError(f"Source file is unavailable: {source_path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise SafetyError(f"Source is not a regular file: {source_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target_path.name}.",
        suffix=".tmp",
        dir=target_path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output, source_path.open("rb") as input_stream:
            shutil.copyfileobj(input_stream, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        shutil.copystat(source_path, temporary, follow_symlinks=False)
        os.replace(temporary, target_path)
        _fsync_directory(target_path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def storage_component(value: str, *, fallback: str = "0") -> str:
    """Create a collision-resistant safe directory component for display text."""

    text = str(value or fallback)
    cleaned = "".join(
        char if char.isalnum() or char in ".-_" else "-" for char in text.casefold()
    ).strip("-.")
    cleaned = cleaned[:72] or fallback
    if cleaned == text.casefold() and cleaned not in {".", ".."}:
        return cleaned
    suffix = hashlib.sha256(text.encode("utf-8", errors="surrogateescape")).hexdigest()[:10]
    return f"{cleaned}-{suffix}"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

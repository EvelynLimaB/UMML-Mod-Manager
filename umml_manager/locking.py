from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType


class LockError(RuntimeError):
    """Raised when another process already owns a manager operation lock."""


class FileLock:
    """Small non-blocking advisory lock for GUI/CLI coordination."""

    def __init__(self, path: str | Path, *, purpose: str):
        self.path = Path(path)
        self.purpose = purpose
        self._stream = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                if stream.read(1) == b"":
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            stream.close()
            raise LockError(
                f"Another UMML Manager process is already {self.purpose}. "
                f"Close it or wait for it to finish. Lock: {self.path}"
            ) from exc

        # Windows msvcrt locks a byte range rather than the whole file. Keep the
        # sentinel byte at offset zero intact and write human-readable ownership
        # metadata after it. Truncating the locked byte made LK_UNLCK fail with
        # PermissionError even though the same process still owned the handle.
        stream.seek(1 if os.name == "nt" else 0)
        stream.truncate()
        stream.write(f"pid={os.getpid()} purpose={self.purpose}\n".encode("utf-8"))
        stream.flush()
        self._stream = stream
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()

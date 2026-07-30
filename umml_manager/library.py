from __future__ import annotations

import os
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import store as _store
from .locking import FileLock, LockError
from .manifest import ManifestError, normalize_manifest_policy
from .models import ModRecord, SourceSpec
from .options import OptionError


class UnrecognizedModError(_store.StoreError):
    """Raised when a package contains no supported UMML or Hachimi root."""


_BaseManagerStore = getattr(
    _store,
    "_UMML_BASE_MANAGER_STORE",
    _store.ManagerStore,
)
_store._UMML_BASE_MANAGER_STORE = _BaseManagerStore  # type: ignore[attr-defined]

_base_find_mod_root = getattr(
    _store,
    "_UMML_BASE_FIND_MOD_ROOT",
    _store.find_mod_root,
)
_store._UMML_BASE_FIND_MOD_ROOT = _base_find_mod_root  # type: ignore[attr-defined]

_base_default_root = getattr(
    _store,
    "_UMML_BASE_DEFAULT_ROOT",
    _store.default_root,
)
_store._UMML_BASE_DEFAULT_ROOT = _base_default_root  # type: ignore[attr-defined]

_IMPORT_MUTEX = threading.RLock()


def find_mod_root(extracted: Path) -> Path:
    try:
        return _base_find_mod_root(extracted)
    except _store.StoreError as exc:
        if str(exc).startswith("No recognizable UMML/Hachimi mod folder"):
            raise UnrecognizedModError(str(exc)) from exc
        raise


def default_root() -> Path:
    """Return the platform-native Manager state root without stranding previews."""

    if not sys.platform.startswith("win"):
        return _base_default_root()
    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    preferred = (
        Path(local_app_data).expanduser() / "UMML Manager"
        if local_app_data
        else Path.home() / "AppData" / "Local" / "UMML Manager"
    )
    legacy = Path.home() / ".local" / "share" / "umml-manager"
    # Early source previews used the Linux-style root even on Windows. Preserve
    # that existing library until the user deliberately migrates it rather than
    # presenting an apparently empty Manager after upgrade.
    if legacy.exists() and not preferred.exists():
        return legacy
    return preferred


class ManagerStore(_BaseManagerStore):
    """Manager store with serialized immutable imports and creator-policy validation.

    Threads in one manager process wait on the local mutex. A separate manager
    process still receives the normal fail-fast advisory-lock error instead of
    waiting indefinitely behind an invisible application.
    """

    def import_folder(
        self,
        folder: str | Path,
        *,
        mod_id: str | None = None,
        source: SourceSpec | None = None,
        metadata_overrides: dict[str, Any] | None = None,
    ) -> ModRecord:
        selected = Path(folder).expanduser().resolve()
        if selected.is_dir() and not _store.is_mod_root(selected):
            selected = find_mod_root(selected)

        # Validate all creator-facing policy before the low-level store copies or
        # registers anything. Invalid options, targeting, dependencies, regions,
        # or ordering must not leave a half-imported immutable record.
        metadata = _store.read_mod_metadata(selected) if selected.is_dir() else {}
        if metadata_overrides:
            metadata.update(
                {
                    key: value
                    for key, value in metadata_overrides.items()
                    if value not in (None, "")
                }
            )
        declared_id = str(mod_id or metadata.get("id") or "")
        try:
            policy = normalize_manifest_policy(metadata, mod_id=declared_id)
        except (ManifestError, OptionError) as exc:
            raise _store.StoreError(f"Invalid UMML package manifest: {exc}") from exc

        with _IMPORT_MUTEX:
            try:
                with FileLock(
                    self.paths.locks / "imports.lock",
                    purpose="allocating and importing an immutable mod version",
                ):
                    record = super().import_folder(
                        selected,
                        mod_id=mod_id,
                        source=source,
                        metadata_overrides=metadata_overrides,
                    )
                    # The low-level store intentionally understands only common
                    # metadata. Enrich the record at the public library boundary
                    # after the whole source import has succeeded.
                    enriched = replace(
                        record,
                        option_groups=policy.option_groups,
                        targets=policy.targets,
                        tags=policy.tags,
                        regions=policy.regions,
                        dependencies=policy.dependencies,
                        incompatibilities=policy.incompatibilities,
                        load_after=policy.load_after,
                        load_before=policy.load_before,
                        compatibility_notes=policy.compatibility_notes,
                    )
                    if enriched.to_dict() != record.to_dict():
                        self.save_mod(enriched)
                    return enriched
            except LockError as exc:
                raise _store.StoreError(str(exc)) from exc


# Compatibility bridge for modules that historically imported from store.py.
# Package initialization loads this boundary before GUI/CLI/provider modules.
_store.find_mod_root = find_mod_root
_store.ManagerStore = ManagerStore
_store.default_root = default_root

StoreError = _store.StoreError

__all__ = [
    "ManagerStore",
    "StoreError",
    "UnrecognizedModError",
    "default_root",
    "find_mod_root",
]

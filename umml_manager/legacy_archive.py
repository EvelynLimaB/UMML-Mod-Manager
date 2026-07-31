from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .models import SourceSpec
from .safety import SafetyError, atomic_copy_file, atomic_write_json, validate_regular_tree
from .store import ManagerStore, StoreError, extract_archive

_ASSET_SUFFIXES = {".acb", ".awb", ".usm", ".bundle", ".unity3d"}
_METADATA_NAMES = {"umml-mod.json", "setting.json", "setting.yml", "setting.yaml"}
_BLOCKED_SUFFIXES = {
    ".appimage",
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".dylib",
    ".exe",
    ".jar",
    ".msi",
    ".ps1",
    ".py",
    ".sh",
    ".so",
}
_HEX_NAME = re.compile(r"^[0-9a-fA-F]{32,128}$")


def import_loose_legacy_archive(
    store: ManagerStore,
    archive: str | Path,
    *,
    mod_id: str,
    source: SourceSpec,
    metadata_overrides: dict[str, Any],
):
    """Import a provider-confirmed loose UMML asset archive safely.

    Some older GameBanana packages contain the files that users historically
    selected with UMML's manual loader, but omit the modern ``assets/`` wrapper
    and manifest. This adapter accepts only archives containing plausible Unity
    asset payloads and rejects executable/native content before constructing a
    normalized immutable package.
    """

    archive_path = Path(archive).expanduser().resolve()
    temporary = Path(
        tempfile.mkdtemp(prefix="umml-loose-import-", dir=store.paths.root)
    )
    try:
        extracted = temporary / "extracted"
        extract_archive(archive_path, extracted)
        payload = _unwrap_single_directory(extracted)
        try:
            validate_regular_tree(payload)
        except SafetyError as exc:
            raise StoreError(str(exc)) from exc

        files = sorted(item for item in payload.rglob("*") if item.is_file())
        if not files:
            raise StoreError("Downloaded archive contains no files")

        blocked = [
            item.relative_to(payload).as_posix()
            for item in files
            if item.suffix.casefold() in _BLOCKED_SUFFIXES
        ]
        if blocked:
            sample = ", ".join(blocked[:5])
            raise StoreError(
                "Loose legacy asset import rejected executable or native content: "
                + sample
            )

        evidence = [item for item in files if _looks_like_game_asset(item)]
        if not evidence:
            raise StoreError(
                "The archive has no assets/ wrapper and does not contain a "
                "recognizable UnityFS, audio, video, or hashed UMML asset payload."
            )

        normalized = temporary / "normalized"
        assets = normalized / "assets"
        assets.mkdir(parents=True)
        entries = list(payload.iterdir())
        for item in entries:
            if item.name.casefold() in _METADATA_NAMES and item.is_file():
                atomic_copy_file(item, normalized / item.name)
                continue
            destination = assets / item.name
            if item.is_dir():
                shutil.copytree(item, destination, symlinks=True)
            else:
                atomic_copy_file(item, destination)

        try:
            validate_regular_tree(normalized)
        except SafetyError as exc:
            raise StoreError(str(exc)) from exc

        if not any((normalized / name).is_file() for name in _METADATA_NAMES):
            atomic_write_json(
                normalized / "umml-mod.json",
                {
                    "id": mod_id,
                    "title": str(metadata_overrides.get("title") or mod_id),
                    "author": str(metadata_overrides.get("author") or ""),
                    "description": str(
                        metadata_overrides.get("description")
                        or "Imported from a loose legacy UMML asset archive."
                    ),
                    "mod_version": str(
                        metadata_overrides.get("mod_version") or "0"
                    ),
                    "regions": list(metadata_overrides.get("regions") or []),
                    "package_type": "umml-assets",
                    "normalized_from": "loose-legacy-archive",
                },
            )

        return store.import_folder(
            normalized,
            mod_id=mod_id,
            source=source,
            metadata_overrides=metadata_overrides,
        )
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _unwrap_single_directory(root: Path) -> Path:
    current = root
    for _ in range(4):
        entries = [item for item in current.iterdir()]
        directories = [item for item in entries if item.is_dir()]
        files = [item for item in entries if item.is_file()]
        if files or len(directories) != 1:
            break
        current = directories[0]
    return current


def _looks_like_game_asset(path: Path) -> bool:
    suffix = path.suffix.casefold()
    if suffix in _ASSET_SUFFIXES:
        return True
    if _HEX_NAME.fullmatch(path.name):
        return True
    try:
        with path.open("rb") as stream:
            return stream.read(8).startswith(b"UnityFS")
    except OSError:
        return False

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from .discovery import is_mod_root, scan_mod_candidates
from .locking import FileLock, LockError
from .models import (
    PACKAGE_HACHIMI,
    PACKAGE_UMML_ASSETS,
    PACKAGE_UNKNOWN,
    ModRecord,
    Profile,
    SourceSpec,
)
from .safety import (
    SafetyError,
    atomic_copy_file,
    atomic_write_json,
    hash_file,
    normalize_relative_path,
    path_under,
    storage_component,
    tree_digest,
    validate_regular_tree,
)

REGISTRY_VERSION = 2
PROFILE_VERSION = 2
SETTINGS_VERSION = 1
WORKSPACE_VERSION = 1
MAX_ARCHIVE_ENTRIES = 20_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBER_NAME = 4096


class StoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManagerPaths:
    root: Path
    registry: Path
    sources: Path
    prepared: Path
    profiles: Path
    settings: Path
    workspaces: Path
    state: Path
    baseline: Path
    transactions: Path
    locks: Path

    @classmethod
    def at(cls, root: str | Path) -> "ManagerPaths":
        root_path = Path(root).expanduser()
        return cls(
            root=root_path,
            registry=root_path / "mods.json",
            sources=root_path / "sources",
            prepared=root_path / "prepared",
            profiles=root_path / "profiles.json",
            settings=root_path / "settings.json",
            workspaces=root_path / "workspaces",
            state=root_path / "active.json",
            baseline=root_path / "baseline",
            transactions=root_path / "transactions",
            locks=root_path / "locks",
        )


class ManagerStore:
    def __init__(self, root: str | Path, *, create: bool = True):
        self.paths = ManagerPaths.at(root)
        if create:
            self.paths.root.mkdir(parents=True, exist_ok=True)
        self.settings_warning = ""

    def list_mods(self) -> list[ModRecord]:
        data = _read_json_object(
            self.paths.registry,
            {"version": REGISTRY_VERSION, "mods": []},
            strict=True,
        )
        _require_document_version(
            data,
            supported=REGISTRY_VERSION,
            label="mod registry",
            path=self.paths.registry,
        )
        raw = data.get("mods", [])
        if not isinstance(raw, list):
            raise StoreError(
                f"Manager mod registry has an invalid mods list: {self.paths.registry}"
            )
        try:
            records = [ModRecord.from_dict(item) for item in raw]
        except (TypeError, ValueError, KeyError) as exc:
            raise StoreError(
                f"Manager mod registry contains an invalid record: {exc}"
            ) from exc
        seen: set[str] = set()
        for record in records:
            _validate_record_identity(record)
            if record.id in seen:
                raise StoreError(
                    f"Manager mod registry contains duplicate ID: {record.id}"
                )
            seen.add(record.id)
        return records

    def get_mod(self, mod_id: str) -> ModRecord:
        for record in self.list_mods():
            if record.id == mod_id:
                return record
        raise StoreError(f"Unknown mod: {mod_id}")

    def save_mod(self, record: ModRecord) -> None:
        _validate_record_identity(record)
        try:
            with FileLock(
                self.paths.locks / "registry.lock",
                purpose="updating the mod library",
            ):
                mods = {item.id: item for item in self.list_mods()}
                mods[record.id] = record
                _write_document(
                    self.paths.registry,
                    {
                        "version": REGISTRY_VERSION,
                        "mods": [
                            mods[key].to_dict() for key in sorted(mods)
                        ],
                    },
                )
        except LockError as exc:
            raise StoreError(str(exc)) from exc

    def remove_mod(self, mod_id: str) -> None:
        try:
            with FileLock(
                self.paths.locks / "registry.lock",
                purpose="updating the mod library",
            ):
                mods = [
                    record
                    for record in self.list_mods()
                    if record.id != mod_id
                ]
                _write_document(
                    self.paths.registry,
                    {
                        "version": REGISTRY_VERSION,
                        "mods": [record.to_dict() for record in mods],
                    },
                )
        except LockError as exc:
            raise StoreError(str(exc)) from exc

    def list_profiles(self) -> list[Profile]:
        data = _read_json_object(
            self.paths.profiles,
            {
                "version": PROFILE_VERSION,
                "profiles": [{"name": "Default", "enabled": []}],
            },
            strict=True,
        )
        _require_document_version(
            data,
            supported=PROFILE_VERSION,
            label="profile registry",
            path=self.paths.profiles,
        )
        raw = data.get("profiles", [])
        if not isinstance(raw, list):
            raise StoreError(
                f"Manager profile registry has an invalid profiles list: {self.paths.profiles}"
            )
        try:
            profiles = [Profile.from_dict(item) for item in raw]
        except (TypeError, ValueError, KeyError) as exc:
            raise StoreError(
                f"Manager profile registry contains an invalid profile: {exc}"
            ) from exc
        seen: set[str] = set()
        for profile in profiles:
            profile.name = profile.name.strip()
            if not profile.name:
                raise StoreError(
                    "Manager profile registry contains an empty profile name"
                )
            if profile.name in seen:
                raise StoreError(
                    f"Manager profile registry contains duplicate name: {profile.name}"
                )
            profile.enabled = _deduplicate(profile.enabled)
            seen.add(profile.name)
        return profiles

    def get_profile(self, name: str) -> Profile:
        for profile in self.list_profiles():
            if profile.name == name:
                return profile
        raise StoreError(f"Unknown profile: {name}")

    def save_profile(self, profile: Profile) -> None:
        profile.name = profile.name.strip()
        if not profile.name:
            raise StoreError("Profile name cannot be empty")
        profile.enabled = _deduplicate(profile.enabled)
        try:
            with FileLock(
                self.paths.locks / "profiles.lock",
                purpose="updating profiles",
            ):
                profiles = {
                    item.name: item for item in self.list_profiles()
                }
                profiles[profile.name] = profile
                _write_document(
                    self.paths.profiles,
                    {
                        "version": PROFILE_VERSION,
                        "profiles": [
                            profiles[key].to_dict()
                            for key in sorted(profiles)
                        ],
                    },
                )
        except LockError as exc:
            raise StoreError(str(exc)) from exc

    def load_settings(self, *, repair: bool = True) -> dict[str, Any]:
        data, warning = _read_settings(
            self.paths.settings,
            repair=repair,
        )
        self.settings_warning = warning
        return data

    def save_settings(self, values: dict[str, Any]) -> None:
        try:
            with FileLock(
                self.paths.locks / "settings.lock",
                purpose="updating settings",
            ):
                current = self.load_settings()
                current.update(values)
                current["version"] = SETTINGS_VERSION
                _write_document(self.paths.settings, current)
                self.settings_warning = ""
        except LockError as exc:
            raise StoreError(str(exc)) from exc

    def source_destination(self, mod_id: str, version: str) -> Path:
        return (
            self.paths.sources
            / sanitize_id(mod_id)
            / storage_component(version)
        )

    def prepared_destination(self, record: ModRecord) -> Path:
        return (
            self.paths.prepared
            / sanitize_id(record.id)
            / storage_component(record.version)
        )

    def import_folder(
        self,
        folder: str | Path,
        *,
        mod_id: str | None = None,
        source: SourceSpec | None = None,
        metadata_overrides: dict[str, Any] | None = None,
    ) -> ModRecord:
        selected = Path(folder).expanduser().resolve()
        if not selected.is_dir():
            raise StoreError(f"Mod folder not found: {selected}")
        if not is_mod_root(selected):
            selected = find_mod_root(selected)
        try:
            validate_regular_tree(selected)
        except SafetyError as exc:
            raise StoreError(str(exc)) from exc

        metadata = read_mod_metadata(selected)
        if metadata_overrides:
            metadata.update(
                {
                    key: value
                    for key, value in metadata_overrides.items()
                    if value not in (None, "")
                }
            )
        base_id = sanitize_id(
            mod_id
            or metadata.get("id")
            or metadata.get("title")
            or selected.name
        )
        version = str(
            metadata.get("mod_version")
            or metadata.get("version")
            or "0"
        )
        existing = self.list_mods()
        existing_by_id = {record.id: record for record in existing}
        chosen_id = _available_record_id(base_id, version, existing)
        existing_record = existing_by_id.get(chosen_id)
        destination = self.source_destination(chosen_id, version)
        try:
            incoming_digest = tree_digest(selected)
            if destination.exists():
                if incoming_digest != tree_digest(destination):
                    raise StoreError(
                        f"Immutable source already exists for {chosen_id} {version} "
                        "with different contents. Change the mod version or import "
                        "it with a different ID."
                    )
                if (
                    existing_record is not None
                    and existing_record.version == version
                    and Path(existing_record.source_path).expanduser().resolve()
                    == destination.resolve()
                ):
                    return existing_record
            else:
                _copy_tree_atomic(
                    selected,
                    destination,
                    expected_digest=incoming_digest,
                )
        except SafetyError as exc:
            raise StoreError(str(exc)) from exc

        package_type = _package_type(selected)
        capabilities = _capabilities(package_type)
        record = ModRecord(
            id=chosen_id,
            name=str(metadata.get("title") or base_id),
            version=version,
            description=str(metadata.get("description") or ""),
            author=str(
                metadata.get("author")
                or metadata.get("submitter")
                or ""
            ),
            regions=_regions(metadata),
            source=source or SourceSpec(),
            source_path=str(destination),
            imported_at=_now(),
            package_type=package_type,
            capabilities=capabilities,
            dependencies=_string_values(metadata.get("dependencies", [])),
            incompatibilities=_string_values(
                metadata.get("incompatibilities", [])
            ),
        )
        self.save_mod(record)
        return record

    def import_archive(
        self,
        archive: str | Path,
        *,
        mod_id: str | None = None,
        source: SourceSpec | None = None,
        metadata_overrides: dict[str, Any] | None = None,
    ) -> ModRecord:
        archive_path = Path(archive).expanduser().resolve()
        try:
            mode = archive_path.lstat().st_mode
        except OSError as exc:
            raise StoreError(f"Archive not found: {archive_path}") from exc
        if not stat.S_ISREG(mode):
            raise StoreError(
                f"Archive is not a regular file: {archive_path}"
            )
        archive_source = source or SourceSpec()
        archive_source = replace(
            archive_source,
            file_name=archive_source.file_name or archive_path.name,
            sha256=archive_source.sha256 or hash_file(archive_path),
            size_bytes=(
                archive_source.size_bytes
                if archive_source.size_bytes is not None
                else archive_path.stat().st_size
            ),
            fetched_at=archive_source.fetched_at or _now(),
        )
        temporary = Path(
            tempfile.mkdtemp(prefix="umml-import-", dir=self.paths.root)
        )
        try:
            extract_archive(archive_path, temporary)
            root = find_mod_root(temporary)
            return self.import_folder(
                root,
                mod_id=mod_id,
                source=archive_source,
                metadata_overrides=metadata_overrides,
            )
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

    def create_workspace(self, mod_id: str) -> Path:
        record = self.get_mod(mod_id)
        source = Path(record.source_path)
        if not source.is_dir():
            raise StoreError(
                f"Source files are missing for {record.name}"
            )
        try:
            source_digest = tree_digest(source)
        except SafetyError as exc:
            raise StoreError(str(exc)) from exc
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        destination = (
            self.paths.workspaces / sanitize_id(mod_id) / stamp
        )
        try:
            _copy_tree_atomic(
                source,
                destination,
                expected_digest=source_digest,
            )
        except SafetyError as exc:
            raise StoreError(str(exc)) from exc
        marker = {
            "version": WORKSPACE_VERSION,
            "base_mod_id": record.id,
            "base_version": record.version,
            "base_source_sha256": source_digest,
            "created_at": _now(),
            "instructions": (
                "Edit this copy, then change its version or ID before importing "
                "it as a new immutable local mod."
            ),
        }
        atomic_write_json(
            destination / ".umml-workspace.json",
            marker,
        )
        return destination


def default_root() -> Path:
    base = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")
    )
    return base / "umml-manager"


def sanitize_id(value: str) -> str:
    cleaned = re.sub(
        r"[^a-z0-9._-]+",
        "-",
        str(value).casefold(),
    ).strip("-.")
    if not cleaned:
        raise StoreError("Could not derive a stable mod ID")
    return cleaned[:96]


def read_mod_metadata(root: Path) -> dict[str, Any]:
    for name in ("umml-mod.json", "setting.json"):
        path = root / name
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise StoreError(f"Invalid {name}: {exc}") from exc
            if not isinstance(data, dict):
                raise StoreError(
                    f"Invalid {name}: top-level value must be an object"
                )
            return data
    for name in ("setting.yml", "setting.yaml"):
        yaml_path = root / name
        if yaml_path.is_file():
            try:
                import yaml

                data = yaml.safe_load(
                    yaml_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                raise StoreError(f"Invalid {name}: {exc}") from exc
            if not isinstance(data, dict):
                raise StoreError(
                    f"Invalid {name}: top-level value must be an object"
                )
            return data
    return {"title": root.name, "mod_version": "0"}


def find_mod_root(extracted: Path) -> Path:
    if is_mod_root(extracted):
        return extracted
    candidates = scan_mod_candidates(
        [extracted],
        max_depth=8,
        include_archives=False,
    )
    if not candidates:
        raise StoreError(
            f"No recognizable UMML/Hachimi mod folder found under {extracted}"
        )
    minimum_depth = min(
        len(item.path.relative_to(extracted).parts)
        for item in candidates
    )
    nearest = [
        item
        for item in candidates
        if len(item.path.relative_to(extracted).parts) == minimum_depth
    ]
    if len(nearest) > 1:
        names = ", ".join(
            str(item.path.relative_to(extracted))
            for item in nearest[:5]
        )
        raise StoreError(
            "Multiple mod folders were found. Import them separately instead "
            "of guessing: "
            + names
        )
    return nearest[0].path


def extract_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive):
        _extract_zip(archive, destination)
        return
    if tarfile.is_tarfile(archive):
        _extract_tar(archive, destination)
        return
    raise StoreError("Unsupported archive; use ZIP or TAR")


def _extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as package:
        members = package.infolist()
        _check_archive_limits(
            archive,
            len(members),
            sum(max(0, member.file_size) for member in members),
        )
        seen: set[str] = set()
        actual = 0
        for member in members:
            relative = _safe_member(member.filename)
            if relative in seen and not member.is_dir():
                raise StoreError(
                    f"Archive contains duplicate file path: {relative}"
                )
            seen.add(relative)
            if member.flag_bits & 0x1:
                raise StoreError(
                    f"Encrypted ZIP entry is unsupported: {member.filename}"
                )
            mode_type = stat.S_IFMT(member.external_attr >> 16)
            if mode_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise StoreError(
                    f"Archive special file rejected: {member.filename}"
                )
            target = path_under(destination, relative)
            if member.is_dir() or member.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            with package.open(member, "r") as source:
                actual = _extract_stream(
                    source,
                    target,
                    actual,
                    archive,
                )


def _extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive) as package:
        members = package.getmembers()
        _check_archive_limits(
            archive,
            len(members),
            sum(
                max(0, member.size)
                for member in members
                if member.isfile()
            ),
        )
        seen: set[str] = set()
        actual = 0
        for member in members:
            relative = _safe_member(member.name)
            if relative in seen and member.isfile():
                raise StoreError(
                    f"Archive contains duplicate file path: {relative}"
                )
            seen.add(relative)
            if not (member.isfile() or member.isdir()):
                raise StoreError(
                    "Archive link, device, or special file rejected: "
                    + member.name
                )
            target = path_under(destination, relative)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            source = package.extractfile(member)
            if source is None:
                raise StoreError(
                    f"Could not read archive member: {member.name}"
                )
            with source:
                actual = _extract_stream(
                    source,
                    target,
                    actual,
                    archive,
                )


def _extract_stream(
    source: BinaryIO,
    target: Path,
    total: int,
    archive: Path,
) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise StoreError(
                        "Archive expanded beyond the "
                        f"{MAX_ARCHIVE_UNCOMPRESSED_BYTES // (1024 ** 3)} GiB "
                        f"safety limit: {archive.name}"
                    )
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return total


def _safe_member(name: str) -> str:
    normalized = name.replace("\\", "/").rstrip("/")
    if len(normalized) > MAX_ARCHIVE_MEMBER_NAME:
        raise StoreError("Archive member name is unreasonably long")
    try:
        return normalize_relative_path(normalized)
    except SafetyError as exc:
        raise StoreError(
            f"Unsafe archive path rejected: {name!r}"
        ) from exc


def _check_archive_limits(
    archive: Path,
    count: int,
    expanded_bytes: int,
) -> None:
    if count > MAX_ARCHIVE_ENTRIES:
        raise StoreError(
            f"Archive contains {count:,} entries; the safety limit is "
            f"{MAX_ARCHIVE_ENTRIES:,}: {archive.name}"
        )
    if expanded_bytes > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        gib = expanded_bytes / (1024 * 1024 * 1024)
        limit = MAX_ARCHIVE_UNCOMPRESSED_BYTES / (1024 * 1024 * 1024)
        raise StoreError(
            f"Archive expands to {gib:.2f} GiB; the safety limit is "
            f"{limit:.0f} GiB: {archive.name}"
        )


def _available_record_id(
    base_id: str,
    version: str,
    existing: list[ModRecord],
) -> str:
    records = {record.id: record for record in existing}
    current = records.get(base_id)
    if current is None or current.version == version:
        return base_id
    suffix = storage_component(version)
    candidate = sanitize_id(f"{base_id}-{suffix}")
    counter = 2
    while candidate in records and records[candidate].version != version:
        candidate = sanitize_id(f"{base_id}-{suffix}-{counter}")
        counter += 1
    return candidate


def _copy_tree_atomic(
    source: Path,
    destination: Path,
    *,
    expected_digest: str,
) -> None:
    validate_regular_tree(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}-",
            dir=destination.parent,
        )
    )
    try:
        content = temporary / "content"
        # Copy links as links so a source tree changed after validation cannot
        # cause copytree to follow a newly introduced path outside the package.
        shutil.copytree(source, content, symlinks=True)
        validate_regular_tree(content)
        copied_digest = tree_digest(content)
        if copied_digest != expected_digest:
            raise StoreError(
                "The source folder changed while it was being copied. Nothing "
                "was imported; retry after the folder is stable."
            )
        if destination.exists():
            raise StoreError(
                f"Immutable source destination already exists: {destination}"
            )
        os.replace(content, destination)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _read_json_object(
    path: Path,
    default: dict[str, Any],
    *,
    strict: bool,
) -> dict[str, Any]:
    if not path.is_file():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise StoreError(
                f"Manager state file is unreadable: {path}. It was not replaced "
                "or reset."
            ) from exc
        return dict(default)
    if not isinstance(data, dict):
        if strict:
            raise StoreError(
                f"Manager state file must contain an object: {path}"
            )
        return dict(default)
    return data


def _read_settings(
    path: Path,
    *,
    repair: bool = True,
) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        return {"version": SETTINGS_VERSION}, ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if not repair:
            return (
                {"version": SETTINGS_VERSION},
                f"Settings are unreadable and were not changed: {path}: {exc}",
            )
        preserved = _quarantine_file(path)
        return (
            {"version": SETTINGS_VERSION},
            f"Settings were unreadable and reset. Original preserved at "
            f"{preserved}: {exc}",
        )
    if not isinstance(data, dict):
        if not repair:
            return (
                {"version": SETTINGS_VERSION},
                f"Settings do not contain an object and were not changed: {path}",
            )
        preserved = _quarantine_file(path)
        return (
            {"version": SETTINGS_VERSION},
            "Settings did not contain an object and were reset. Original "
            f"preserved at {preserved}.",
        )
    try:
        _require_document_version(
            data,
            supported=SETTINGS_VERSION,
            label="settings",
            path=path,
        )
    except StoreError as exc:
        if not repair:
            return (
                {"version": SETTINGS_VERSION},
                f"Settings use an unsupported schema and were not changed: "
                f"{path}: {exc}",
            )
        preserved = _quarantine_file(path)
        return (
            {"version": SETTINGS_VERSION},
            f"Settings used an unsupported schema and were reset. Original "
            f"preserved at {preserved}: {exc}",
        )
    data.setdefault("version", SETTINGS_VERSION)
    return data, ""


def _quarantine_file(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        atomic_copy_file(path, destination)
    except SafetyError as exc:
        raise StoreError(
            f"Could not preserve unreadable settings file {path}: {exc}"
        ) from exc
    return destination


def _require_document_version(
    data: dict[str, Any],
    *,
    supported: int,
    label: str,
    path: Path,
) -> int:
    try:
        version = int(data.get("version", 1))
    except (TypeError, ValueError) as exc:
        raise StoreError(
            f"Manager {label} has an invalid schema version: {path}"
        ) from exc
    if version < 1 or version > supported:
        raise StoreError(
            f"Manager {label} uses schema version {version}, but this build "
            f"supports up to {supported}: {path}"
        )
    return version


def _write_document(path: Path, data: dict[str, Any]) -> None:
    if path.is_file():
        try:
            atomic_copy_file(
                path,
                path.with_suffix(path.suffix + ".bak"),
            )
        except SafetyError as exc:
            raise StoreError(
                f"Could not preserve state backup for {path}: {exc}"
            ) from exc
    atomic_write_json(path, data)


def _package_type(root: Path) -> str:
    assets = root / "assets"
    if assets.is_dir() and any(
        item.is_file() for item in assets.rglob("*")
    ):
        return PACKAGE_UMML_ASSETS
    hachimi = root / "hachimi"
    if hachimi.is_dir() and any(
        item.is_file() for item in hachimi.rglob("*")
    ):
        return PACKAGE_HACHIMI
    return PACKAGE_UNKNOWN


def _capabilities(package_type: str) -> list[str]:
    if package_type == PACKAGE_UMML_ASSETS:
        return ["prepare-assets", "deploy-files"]
    if package_type == PACKAGE_HACHIMI:
        return ["hachimi-runtime"]
    return []


def _validate_record_identity(record: ModRecord) -> None:
    if sanitize_id(record.id) != record.id:
        raise StoreError(
            f"Mod record has an unsafe ID: {record.id!r}"
        )
    if not record.name.strip():
        raise StoreError(
            f"Mod record has an empty name: {record.id}"
        )


def _regions(metadata: dict[str, Any]) -> list[str]:
    value = metadata.get("regions", metadata.get("region", []))
    return _string_values(value)


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return []


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

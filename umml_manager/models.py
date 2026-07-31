from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .manifest import normalize_manifest_policy

PACKAGE_UMML_ASSETS = "umml-assets"
PACKAGE_HACHIMI = "hachimi"
PACKAGE_UNKNOWN = "unknown"
SUPPORTED_UPDATE_POLICIES = {"notify", "download", "manual"}


def _asset_capabilities() -> list[str]:
    return ["prepare-assets", "deploy-files"]


@dataclass(frozen=True)
class SourceSpec:
    provider: str = "local"
    url: str = ""
    submission_id: int | None = None
    file_id: int | None = None
    updated_at: int | None = None
    file_name: str = ""
    sha256: str = ""
    size_bytes: int | None = None
    fetched_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SourceSpec":
        if data is None:
            data = {}
        elif not isinstance(data, dict):
            raise ValueError("Source specification must be an object")
        return cls(
            provider=str(data.get("provider", "local")),
            url=str(data.get("url", "")),
            submission_id=_optional_int(data.get("submission_id")),
            file_id=_optional_int(data.get("file_id")),
            updated_at=_optional_int(data.get("updated_at")),
            file_name=str(data.get("file_name", "")),
            sha256=str(data.get("sha256", "")),
            size_bytes=_optional_int(data.get("size_bytes")),
            fetched_at=str(data.get("fetched_at", "")),
        )


@dataclass
class ModRecord:
    id: str
    name: str
    version: str = "0"
    description: str = ""
    author: str = ""
    regions: list[str] = field(default_factory=list)
    source: SourceSpec = field(default_factory=SourceSpec)
    source_path: str = ""
    prepared_path: str = ""
    # Non-configurable packages and the default configurable selection expose a
    # conventional target -> SHA map for status, compatibility, and migration.
    files: dict[str, str] = field(default_factory=dict)
    # Historical one-source -> one-target compatibility maps. New configurable
    # preparation also records source_payloads because one Unity bundle can expand
    # into several final game targets.
    source_files: dict[str, str] = field(default_factory=dict)
    source_hashes: dict[str, str] = field(default_factory=dict)
    # Creator-facing source -> {final target -> SHA-256}. Each source has its own
    # prepared root, so a profile can enable or disable a whole authored bundle
    # without pretending each final target came from a separate source file.
    source_payloads: dict[str, dict[str, str]] = field(default_factory=dict)
    source_roots: dict[str, str] = field(default_factory=dict)
    # Metadata fingerprint for the last completed source-index attempt. The value is
    # recorded even when a legacy package cannot expose a safe source map, preventing
    # an automatic retry loop while still allowing a retry after metadata changes.
    source_indexed_against: str = ""
    option_groups: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Creator-declared informational targeting. Character/dress entries describe
    # authored compatibility; they do not rewrite arbitrary bundle internals.
    targets: dict[str, list[str]] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    imported_at: str = ""
    update_policy: str = "notify"
    package_type: str = PACKAGE_UMML_ASSETS
    capabilities: list[str] = field(default_factory=_asset_capabilities)
    dependencies: list[str] = field(default_factory=list)
    incompatibilities: list[str] = field(default_factory=list)
    # Conditional ordering constraints. They apply only when both mods are
    # enabled and become visible resolver blockers when the profile order is wrong.
    load_after: list[str] = field(default_factory=list)
    load_before: list[str] = field(default_factory=list)
    compatibility_notes: str = ""
    prepared_against: str = ""
    prepared_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModRecord":
        if not isinstance(data, dict):
            raise ValueError("Mod record must be an object")
        if "id" not in data:
            raise ValueError("Mod record is missing id")
        record_id = str(data["id"])
        policy = normalize_manifest_policy(data, mod_id=record_id)
        update_policy = str(data.get("update_policy", "notify"))
        if update_policy not in SUPPORTED_UPDATE_POLICIES:
            update_policy = "notify"
        package_type = str(data.get("package_type", PACKAGE_UMML_ASSETS))
        capabilities = _string_list(data.get("capabilities", []))
        if "capabilities" not in data:
            capabilities = _default_capabilities(package_type)
        return cls(
            id=record_id,
            name=str(data.get("name") or record_id),
            version=str(data.get("version", "0")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
            regions=policy.regions,
            source=SourceSpec.from_dict(data.get("source")),
            source_path=str(data.get("source_path", "")),
            prepared_path=str(data.get("prepared_path", "")),
            files={
                str(key): str(value)
                for key, value in _mapping(data.get("files", {})).items()
            },
            source_files={
                str(key): str(value)
                for key, value in _mapping(data.get("source_files", {})).items()
            },
            source_hashes={
                str(key): str(value)
                for key, value in _mapping(data.get("source_hashes", {})).items()
            },
            source_payloads=_payload_mapping(data.get("source_payloads", {})),
            source_roots={
                str(key): str(value)
                for key, value in _mapping(data.get("source_roots", {})).items()
            },
            source_indexed_against=str(data.get("source_indexed_against", "")),
            option_groups=policy.option_groups,
            targets=policy.targets,
            tags=policy.tags,
            imported_at=str(data.get("imported_at", "")),
            update_policy=update_policy,
            package_type=package_type,
            capabilities=capabilities,
            dependencies=policy.dependencies,
            incompatibilities=policy.incompatibilities,
            load_after=policy.load_after,
            load_before=policy.load_before,
            compatibility_notes=policy.compatibility_notes,
            prepared_against=str(data.get("prepared_against", "")),
            prepared_at=str(data.get("prepared_at", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Profile:
    name: str
    enabled: list[str] = field(default_factory=list)
    region: str = ""
    installation_key: str = ""
    options: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        if not isinstance(data, dict):
            raise ValueError("Profile must be an object")
        if "name" not in data:
            raise ValueError("Profile is missing name")
        raw_options = _mapping(data.get("options", {}))
        options: dict[str, dict[str, Any]] = {}
        for key, value in raw_options.items():
            if isinstance(value, dict):
                options[str(key)] = dict(value)
        return cls(
            name=str(data["name"]),
            enabled=_string_list(data.get("enabled", [])),
            region=str(data.get("region", "")),
            installation_key=str(data.get("installation_key", "")),
            options=options,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": list(self.enabled),
            "region": self.region,
            "installation_key": self.installation_key,
            "options": {key: dict(value) for key, value in self.options.items()},
        }


def _default_capabilities(package_type: str) -> list[str]:
    if package_type == PACKAGE_UMML_ASSETS:
        return _asset_capabilities()
    if package_type == PACKAGE_HACHIMI:
        return ["hachimi-runtime"]
    return []


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value]


def _mapping(value: object) -> dict[Any, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _payload_mapping(value: object) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for source, raw_payload in _mapping(value).items():
        if not isinstance(raw_payload, dict):
            continue
        payload = {
            str(target): str(sha256)
            for target, sha256 in raw_payload.items()
        }
        if payload:
            result[str(source)] = payload
    return result

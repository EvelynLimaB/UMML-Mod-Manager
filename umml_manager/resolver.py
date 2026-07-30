from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import PACKAGE_UMML_ASSETS, ModRecord, Profile
from .options import OptionError, normalize_profile_options, select_source_paths
from .regions import normalize_region
from .safety import SafetyError, normalize_relative_path, validate_sha256


@dataclass(frozen=True)
class Claim:
    mod_id: str
    mod_version: str
    source_path: str
    sha256: str


@dataclass(frozen=True)
class Conflict:
    path: str
    winner: str
    overridden: tuple[str, ...]


@dataclass
class Resolution:
    profile: str
    target_region: str = ""
    target_installation_key: str = ""
    metadata_fingerprint: str = ""
    winners: dict[str, Claim] = field(default_factory=dict)
    known_mod_hashes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unprepared: list[str] = field(default_factory=list)
    stale_prepared: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    incompatible: list[str] = field(default_factory=list)
    wrong_installation: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)
    invalid_options: list[str] = field(default_factory=list)
    missing_dependencies: list[str] = field(default_factory=list)
    incompatibility_conflicts: list[str] = field(default_factory=list)
    load_order_conflicts: list[str] = field(default_factory=list)

    @property
    def blocking_issues(self) -> list[str]:
        # Option failures are also mirrored into invalid so existing GUI/CLI plan
        # renderers show them under Invalid manifests without a second counting
        # path. invalid_options remains structured evidence for callers/tests.
        return (
            self.missing
            + self.unprepared
            + self.stale_prepared
            + self.unsupported
            + self.incompatible
            + self.wrong_installation
            + self.invalid
            + self.missing_dependencies
            + self.incompatibility_conflicts
            + self.load_order_conflicts
        )


def resolve_profile(
    profile: Profile,
    mods: list[ModRecord],
    *,
    target_region: str = "",
    target_installation_key: str = "",
    metadata_fingerprint: str = "",
) -> Resolution:
    records = {record.id: record for record in mods}
    claims: dict[str, list[Claim]] = {}
    region = normalize_region(target_region or profile.region, default="")
    installation_key = str(target_installation_key or "").strip()
    fingerprint = str(metadata_fingerprint or "").strip().casefold()
    resolution = Resolution(
        profile=profile.name,
        target_region=region,
        target_installation_key=installation_key,
        metadata_fingerprint=fingerprint,
    )
    resolution.known_mod_hashes = _known_mod_hashes(mods)
    if profile.installation_key:
        if not installation_key:
            resolution.wrong_installation.append(
                f"profile is bound to {profile.installation_key}, but the target "
                "installation identity is unverified"
            )
        elif profile.installation_key != installation_key:
            resolution.wrong_installation.append(
                f"profile is bound to {profile.installation_key}, not {installation_key}"
            )
    enabled = _deduplicate_profile(profile.enabled, resolution)
    enabled_set = set(enabled)
    enabled_order = {mod_id: index for index, mod_id in enumerate(enabled)}

    for mod_id in enabled:
        record = records.get(mod_id)
        if record is None:
            resolution.missing.append(mod_id)
            continue
        if (
            record.package_type != PACKAGE_UMML_ASSETS
            or "deploy-files" not in record.capabilities
        ):
            resolution.unsupported.append(
                f"{mod_id} ({record.package_type or 'unknown package type'})"
            )
            continue
        if region and record.regions:
            supported = {
                normalize_region(value, default="")
                for value in record.regions
            }
            if region not in supported:
                resolution.incompatible.append(
                    f"{mod_id} supports {', '.join(record.regions)}, not {region}"
                )
                continue
        missing = [
            dependency
            for dependency in record.dependencies
            if dependency not in enabled_set
        ]
        if missing:
            resolution.missing_dependencies.append(
                f"{mod_id} requires {', '.join(missing)}"
            )
            continue
        conflicts = [
            other
            for other in record.incompatibilities
            if other in enabled_set
        ]
        if conflicts:
            resolution.incompatibility_conflicts.append(
                f"{mod_id} conflicts with {', '.join(conflicts)}"
            )
            continue

        current_index = enabled_order[mod_id]
        must_follow = [
            other
            for other in record.load_after
            if other in enabled_order and current_index <= enabled_order[other]
        ]
        must_precede = [
            other
            for other in record.load_before
            if other in enabled_order and current_index >= enabled_order[other]
        ]
        if must_follow or must_precede:
            details: list[str] = []
            if must_follow:
                details.append("must load after " + ", ".join(must_follow))
            if must_precede:
                details.append("must load before " + ", ".join(must_precede))
            resolution.load_order_conflicts.append(
                f"{mod_id} " + "; ".join(details)
            )
            continue

        if not record.prepared_path:
            resolution.unprepared.append(mod_id)
            continue
        if record.option_groups:
            if not (
                record.files
                and record.source_files
                and record.source_hashes
                and record.source_roots
            ):
                resolution.unprepared.append(
                    f"{mod_id} needs option-aware re-preparation"
                )
                continue
        elif not record.files:
            resolution.unprepared.append(mod_id)
            continue

        prepared_against = str(record.prepared_against or "").strip().casefold()
        if fingerprint and not prepared_against:
            resolution.stale_prepared.append(
                f"{mod_id} has no metadata fingerprint; re-prepare it against "
                f"the current metadata {fingerprint[:12]}…"
            )
            continue
        if fingerprint and prepared_against != fingerprint:
            resolution.stale_prepared.append(
                f"{mod_id} was prepared against {prepared_against[:12]}…, "
                f"current metadata is {fingerprint[:12]}…"
            )
            continue

        if record.option_groups:
            _resolve_configurable_record(
                record,
                profile,
                claims,
                resolution,
            )
            continue

        validated: list[tuple[str, str]] = []
        try:
            for relative, sha256 in sorted(record.files.items()):
                validated.append(
                    (
                        normalize_relative_path(relative),
                        validate_sha256(sha256),
                    )
                )
        except SafetyError as exc:
            resolution.invalid.append(f"{mod_id}: {exc}")
            continue
        for relative, sha256 in validated:
            claims.setdefault(relative, []).append(
                Claim(
                    mod_id=record.id,
                    mod_version=record.version,
                    source_path=record.prepared_path,
                    sha256=sha256,
                )
            )

    for relative, path_claims in claims.items():
        winner = path_claims[-1]
        resolution.winners[relative] = winner
        if len(path_claims) > 1:
            resolution.conflicts.append(
                Conflict(
                    path=relative,
                    winner=winner.mod_id,
                    overridden=tuple(
                        claim.mod_id for claim in path_claims[:-1]
                    ),
                )
            )
    resolution.conflicts.sort(key=lambda item: item.path)
    return resolution


def _resolve_configurable_record(
    record: ModRecord,
    profile: Profile,
    claims: dict[str, list[Claim]],
    resolution: Resolution,
) -> None:
    try:
        selected = normalize_profile_options(
            record.option_groups,
            profile.options.get(record.id, {}),
        )
        selected_sources = select_source_paths(
            record.option_groups,
            selected,
            record.source_files.keys(),
        )
        selected_claims: dict[str, Claim] = {}
        selected_owners: dict[str, str] = {}
        for source in sorted(selected_sources):
            if source not in record.source_hashes or source not in record.source_roots:
                raise OptionError(
                    f"prepared source mapping is incomplete for {source!r}; re-prepare the mod"
                )
            target = normalize_relative_path(record.source_files[source])
            sha256 = validate_sha256(record.source_hashes[source])
            root_relative = normalize_relative_path(record.source_roots[source])
            previous = selected_owners.get(target)
            if previous is not None:
                raise OptionError(
                    "selected sources resolve to the same game target: "
                    f"{previous!r} and {source!r} -> {target}"
                )
            selected_owners[target] = source
            selected_claims[target] = Claim(
                mod_id=record.id,
                mod_version=record.version,
                source_path=str(Path(record.prepared_path) / root_relative),
                sha256=sha256,
            )
    except (OptionError, SafetyError) as exc:
        _record_option_error(resolution, record.id, str(exc))
        return
    if not selected_claims:
        _record_option_error(
            resolution,
            record.id,
            "selected options produced no deployable assets",
        )
        return
    for target, claim in selected_claims.items():
        claims.setdefault(target, []).append(claim)


def _known_mod_hashes(mods: list[ModRecord]) -> dict[str, tuple[str, ...]]:
    known: dict[str, set[str]] = {}
    for record in mods:
        if record.package_type != PACKAGE_UMML_ASSETS:
            continue
        try:
            if record.option_groups and record.source_files and record.source_hashes:
                for source, target in record.source_files.items():
                    if source not in record.source_hashes:
                        continue
                    canonical = normalize_relative_path(target)
                    sha256 = validate_sha256(record.source_hashes[source])
                    known.setdefault(canonical, set()).add(sha256)
            else:
                for relative, sha256 in record.files.items():
                    canonical = normalize_relative_path(relative)
                    known.setdefault(canonical, set()).add(validate_sha256(sha256))
        except SafetyError:
            continue
    return {
        relative: tuple(sorted(hashes))
        for relative, hashes in known.items()
    }


def _record_option_error(
    resolution: Resolution,
    mod_id: str,
    message: str,
) -> None:
    detail = f"{mod_id}: profile options: {message}"
    resolution.invalid_options.append(detail)
    resolution.invalid.append(detail)


def _deduplicate_profile(
    values: list[str],
    resolution: Resolution,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        mod_id = str(value)
        if mod_id in seen:
            resolution.duplicates.append(mod_id)
            continue
        seen.add(mod_id)
        result.append(mod_id)
    return result

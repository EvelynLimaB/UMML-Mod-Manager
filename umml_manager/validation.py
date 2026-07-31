from __future__ import annotations

import json
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .deployment import (
    ApplyEngine,
    ApplyError,
    LegacyBaselineMigrationRequired,
)
from .engine import (
    BASELINE_VERSION,
    JOURNAL_VERSION,
)
from .models import ModRecord, Profile
from .process import running_game_processes
from .resolver import resolve_profile
from .safety import (
    SafetyError,
    atomic_copy_file,
    atomic_write_json,
    hash_file,
    path_under,
    validate_sha256,
)
from .store import ManagerStore

SELF_TEST_FINGERPRINT = "f" * 64
SELF_TEST_INSTALLATION = "self-test"


class ValidationError(RuntimeError):
    """Raised when a disposable validation check does not behave as expected."""


def run_disposable_self_test() -> dict[str, object]:
    """Exercise public Manager boundaries without touching user or game data."""

    checks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="umml-manager-self-test-") as temp:
        root = Path(temp)
        _check_imports(root / "imports")
        checks.append("folder-and-zip-import")

        _check_profile_lifecycle(root / "lifecycle")
        checks.extend(
            (
                "profile-conflict-winner",
                "apply-switch-and-restore",
                "external-change-protection",
            )
        )

        _check_legacy_baseline_migration(root / "legacy")
        checks.append("legacy-baseline-migration")

        _check_interrupted_recovery(root / "recovery")
        checks.append("interrupted-transaction-recovery")

    return {
        "status": "passed",
        "checks": checks,
        "temporary_only": True,
        "real_game_files_changed": False,
    }


def collect_manager_diagnostics(
    store: ManagerStore,
    *,
    process_check: Callable[[str | Path | None], tuple] = running_game_processes,
) -> dict[str, object]:
    """Collect read-only platform, trust, state, and target diagnostics."""

    from .platform_bridge import format_doctor_report

    from .network import tls_diagnostics

    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "detail": detail,
            }
        )

    try:
        platform_report, platform_ready = format_doctor_report()
    except Exception as exc:
        platform_report = f"Platform diagnostics failed: {exc}"
        platform_ready = False
    add("platform-detection", platform_ready, platform_report)

    try:
        tls_report, tls_ready = tls_diagnostics()
    except Exception as exc:
        tls_report = f"HTTPS trust diagnostics failed: {exc}"
        tls_ready = False
    add("https-trust", tls_ready, tls_report)

    try:
        settings = store.load_settings(repair=False)
    except Exception as exc:
        settings = {}
        add("settings", False, str(exc))
    else:
        add(
            "settings",
            not bool(store.settings_warning),
            store.settings_warning or f"valid: {store.paths.settings}",
        )

    try:
        mods = store.list_mods()
        profiles = store.list_profiles()
    except Exception as exc:
        mods = []
        profiles = []
        add("registries", False, str(exc))
    else:
        add(
            "registries",
            True,
            f"{len(mods)} mod record(s); {len(profiles)} profile(s)",
        )

    dat_text = str(settings.get("dat_path", "")).strip()
    game_text = str(settings.get("game_dir", "")).strip()
    meta_text = str(settings.get("meta_path", "")).strip()
    dat = Path(dat_text).expanduser() if dat_text else None
    game = Path(game_text).expanduser() if game_text else None
    meta = Path(meta_text).expanduser() if meta_text else None
    target_ready = bool(
        dat
        and dat.is_dir()
        and game
        and game.is_dir()
        and meta
        and meta.is_file()
    )
    add(
        "saved-target-paths",
        target_ready,
        (
            f"dat={dat or 'not set'}; game={game or 'not set'}; "
            f"meta={meta or 'not set'}"
        ),
    )

    recorded = str(settings.get("metadata_fingerprint", "")).strip()
    fingerprint_ready = False
    fingerprint_detail = "no verified metadata fingerprint"
    if meta is not None and meta.is_file() and recorded:
        try:
            expected = validate_sha256(recorded)
            actual = hash_file(meta)
        except (OSError, SafetyError) as exc:
            fingerprint_detail = str(exc)
        else:
            fingerprint_ready = actual == expected
            fingerprint_detail = (
                f"verified: {actual}"
                if fingerprint_ready
                else f"saved {expected}; current {actual}"
            )
    add("metadata-integrity", fingerprint_ready, fingerprint_detail)

    installation_key = str(settings.get("installation_key", "")).strip()
    add(
        "installation-identity",
        bool(installation_key),
        installation_key or "manual/unverified",
    )

    try:
        running = process_check(game)
    except Exception as exc:
        add("game-process-inspection", False, str(exc))
    else:
        names = ", ".join(
            sorted({getattr(item, "name", "game") for item in running})
        )
        add(
            "game-process-inspection",
            not bool(running),
            f"game running: {names}" if running else "game closed",
        )

    pending: list[str] = []
    if store.paths.transactions.is_dir():
        try:
            pending = sorted(
                path.name
                for path in store.paths.transactions.iterdir()
                if path.is_dir() and path.name.startswith("apply-")
            )
        except OSError as exc:
            add("transactions", False, str(exc))
        else:
            add(
                "transactions",
                not pending,
                (
                    "none"
                    if not pending
                    else "pending: " + ", ".join(pending[:10])
                ),
            )
    else:
        add("transactions", True, "none")

    if dat is not None and dat.is_dir():
        try:
            engine = ApplyEngine(
                store,
                dat,
                game_dir=game,
                process_check=process_check,
            )
            active = engine._read_active_document()
            _validate_real_baseline_scope(
                store,
                target_id=engine.target_id,
                dat=dat.resolve(),
            )
        except Exception as exc:
            add("deployment-state", False, str(exc))
        else:
            add(
                "deployment-state",
                True,
                f"{len(active['files'])} active managed file(s)",
            )
    else:
        add("deployment-state", False, "saved dat directory is unavailable")

    ready = all(bool(check["passed"]) for check in checks)
    return {
        "status": "ready" if ready else "check",
        "ready": ready,
        "data_root": str(store.paths.root),
        "checks": checks,
    }


def run_live_network_smoke(
    *,
    region: str = "global",
    client: Any | None = None,
    preview_loader: Any | None = None,
) -> dict[str, object]:
    """Exercise current GameBanana browse, detail, file, and preview responses."""

    from .preview_images import PreviewImageLoader
    from .providers.gamebanana_previews import PreviewGameBananaClient

    provider = client or PreviewGameBananaClient()
    page = provider.browse(
        region=region,
        page=1,
        per_page=12,
        sort="updated",
        query="",
    )
    if not page.mods:
        raise ValidationError(
            f"GameBanana returned no current {region} mods"
        )

    selected = None
    errors: list[str] = []
    for candidate in page.mods[:8]:
        try:
            detailed = provider.fetch(str(candidate.id))
        except Exception as exc:
            errors.append(f"{candidate.id}: {exc}")
            continue
        if detailed.files and detailed.image_url:
            selected = detailed
            break
    if selected is None:
        detail = "; ".join(errors[:3])
        suffix = f" Detail errors: {detail}" if detail else ""
        raise ValidationError(
            "No recent GameBanana result provided both downloadable files and "
            f"a verified preview URL.{suffix}"
        )

    loader = preview_loader or PreviewImageLoader()
    preview = loader.load(selected.image_url)
    width, height = preview.image.size
    if width <= 0 or height <= 0 or preview.byte_size <= 0:
        raise ValidationError("GameBanana preview decoded with invalid dimensions")

    return {
        "status": "passed",
        "region": region,
        "catalog_records": len(page.mods),
        "submission_id": selected.id,
        "submission_name": selected.name,
        "downloadable_files": len(selected.files),
        "preview_url": preview.source_url,
        "preview_content_type": preview.content_type,
        "preview_bytes": preview.byte_size,
        "preview_size": [width, height],
        "download_executed": False,
        "real_game_files_changed": False,
    }


def verify_profile_on_disposable_copy(
    store: ManagerStore,
    profile: Profile,
    *,
    dat_path: str | Path,
    game_dir: str | Path | None,
    target_region: str,
    target_installation_key: str,
    metadata_fingerprint: str,
    process_check: Callable[[str | Path | None], tuple] = running_game_processes,
) -> dict[str, object]:
    """Apply and restore one real profile on copied target files only.

    The real manager state, baselines, backups, prepared cache, and game files
    are read and hash-checked. All deployment writes occur under a temporary
    directory with a separate ManagerStore.
    """

    dat = Path(dat_path).expanduser().resolve()
    if not dat.is_dir():
        raise ValidationError(f"Game dat directory not found: {dat}")
    try:
        running = process_check(game_dir)
    except Exception as exc:
        raise ValidationError(
            f"Game process inspection failed; disposable verification stopped: {exc}"
        ) from exc
    if running:
        names = ", ".join(
            sorted({getattr(item, "name", "game") for item in running})
        )
        raise ValidationError(
            f"Game is running ({names}); close it before taking a stable validation copy"
        )

    records = store.list_mods()
    resolution = resolve_profile(
        profile,
        records,
        target_region=target_region,
        target_installation_key=target_installation_key,
        metadata_fingerprint=metadata_fingerprint,
    )
    if resolution.blocking_issues:
        raise ValidationError(
            "Profile cannot be verified while it has blockers:\n"
            + "\n".join(resolution.blocking_issues)
        )
    if not resolution.winners:
        raise ValidationError(
            f"Profile {profile.name!r} has no deployable files to verify"
        )

    real_engine = ApplyEngine(
        store,
        dat,
        game_dir=game_dir,
        process_check=process_check,
    )
    active_document = real_engine._read_active_document()
    _validate_real_baseline_scope(
        store,
        target_id=real_engine.target_id,
        dat=dat,
    )
    affected = sorted(set(active_document["files"]) | set(resolution.winners))
    real_before = {
        relative: _file_state(path_under(dat, relative))
        for relative in affected
    }

    with tempfile.TemporaryDirectory(
        prefix="umml-manager-profile-verification-"
    ) as temp:
        root = Path(temp)
        clone_dat = root / "Persistent" / "dat"
        clone_backup = root / "Persistent" / "dat.backup"
        clone_dat.mkdir(parents=True)
        copied_bytes = 0
        for relative in affected:
            copied_bytes += _copy_stable_optional(
                path_under(dat, relative),
                path_under(clone_dat, relative),
            )
            copied_bytes += _copy_stable_optional(
                path_under(dat.parent / "dat.backup", relative),
                path_under(clone_backup, relative),
            )

        isolated = ManagerStore(root / "manager")
        isolated.save_settings({"dat_path": str(clone_dat)})
        clone_engine = ApplyEngine(
            isolated,
            clone_dat,
            process_check=lambda _game: (),
        )
        clone_engine._ensure_baseline_scope()
        for relative in affected:
            _copy_trusted_baseline(
                store,
                isolated,
                relative,
            )

        cloned_active = dict(active_document)
        cloned_active["target_id"] = clone_engine.target_id
        cloned_active["dat_path"] = str(clone_dat.resolve())
        atomic_write_json(isolated.paths.state, cloned_active)

        apply_result = clone_engine.apply(
            resolution,
            import_legacy_baselines=True,
        )
        for relative, claim in resolution.winners.items():
            target = path_under(clone_dat, relative)
            if not target.is_file() or hash_file(target) != claim.sha256:
                raise ValidationError(
                    f"Disposable apply did not install the expected winner: {relative}"
                )

        restore_resolution = resolve_profile(
            Profile(
                "Disposable restore",
                [],
                region=target_region,
                installation_key=target_installation_key,
            ),
            records,
            target_region=target_region,
            target_installation_key=target_installation_key,
            metadata_fingerprint=metadata_fingerprint,
        )
        restore_result = clone_engine.apply(restore_resolution)
        for relative in affected:
            _assert_matches_isolated_baseline(
                isolated,
                clone_dat,
                relative,
            )

    real_after = {
        relative: _file_state(path_under(dat, relative))
        for relative in affected
    }
    if real_after != real_before:
        changed = [
            relative
            for relative in affected
            if real_after[relative] != real_before[relative]
        ]
        raise ValidationError(
            "Real game files changed while the disposable verification was "
            "running; no result can be trusted: "
            + ", ".join(changed[:10])
        )

    return {
        "status": "passed",
        "profile": profile.name,
        "files": len(resolution.winners),
        "affected_files": len(affected),
        "conflicts": len(resolution.conflicts),
        "copied_bytes": copied_bytes,
        "installed": apply_result.installed,
        "unchanged": apply_result.unchanged,
        "imported_legacy_baselines": apply_result.imported_baselines,
        "restored": restore_result.restored,
        "temporary_only": True,
        "real_game_files_changed": False,
    }


def _check_imports(root: Path) -> None:
    source = root / "source"
    assets = source / "assets"
    assets.mkdir(parents=True)
    (assets / "sample.bundle").write_bytes(b"sample-folder-asset")
    (source / "setting.json").write_text(
        json.dumps(
            {
                "title": "Self-test folder",
                "mod_version": "1",
            }
        ),
        encoding="utf-8",
    )

    archive_source = root / "archive-source"
    archive_assets = archive_source / "assets"
    archive_assets.mkdir(parents=True)
    (archive_assets / "sample.bundle").write_bytes(b"sample-archive-asset")
    (archive_source / "setting.json").write_text(
        json.dumps(
            {
                "title": "Self-test archive",
                "mod_version": "1",
            }
        ),
        encoding="utf-8",
    )
    archive = root / "sample.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(archive_source.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(archive_source).as_posix())

    store = ManagerStore(root / "manager")
    folder_record = store.import_folder(source)
    archive_record = store.import_archive(archive)
    _require(folder_record.name == "Self-test folder", "folder import metadata")
    _require(archive_record.name == "Self-test archive", "archive import metadata")
    _require(
        Path(folder_record.source_path).is_dir(),
        "folder immutable source was not preserved",
    )
    _require(
        Path(archive_record.source_path).is_dir(),
        "archive immutable source was not preserved",
    )


def _check_profile_lifecycle(root: Path) -> None:
    dat = root / "game" / "Persistent" / "dat"
    shared = dat / "aa" / "shared"
    first_only = dat / "bb" / "first-only"
    shared.parent.mkdir(parents=True)
    first_only.parent.mkdir(parents=True)
    shared.write_bytes(b"vanilla-shared")
    first_only.write_bytes(b"vanilla-first-only")

    first_root = root / "prepared-first"
    first_shared = first_root / "aa" / "shared"
    first_extra = first_root / "bb" / "first-only"
    first_shared.parent.mkdir(parents=True)
    first_extra.parent.mkdir(parents=True)
    first_shared.write_bytes(b"first-shared")
    first_extra.write_bytes(b"first-only")

    second_root = root / "prepared-second"
    second_shared = second_root / "aa" / "shared"
    second_shared.parent.mkdir(parents=True)
    second_shared.write_bytes(b"second-shared")

    first = _prepared_record(
        "first",
        "First",
        first_root,
        {
            "aa/shared": first_shared,
            "bb/first-only": first_extra,
        },
    )
    second = _prepared_record(
        "second",
        "Second",
        second_root,
        {"aa/shared": second_shared},
    )
    records = [first, second]
    store = ManagerStore(root / "manager")
    store.save_mod(first)
    store.save_mod(second)
    store.save_settings({"dat_path": str(dat)})
    engine = ApplyEngine(store, dat, process_check=lambda _game: ())

    first_resolution = _resolution(Profile("First", ["first"]), records)
    first_result = engine.apply(first_resolution)
    _require(first_result.installed == 2, "first profile did not install two files")
    _require(shared.read_bytes() == b"first-shared", "first shared winner")
    _require(first_only.read_bytes() == b"first-only", "first exclusive winner")

    conflict_resolution = _resolution(
        Profile("Conflict", ["first", "second"]),
        records,
    )
    _require(len(conflict_resolution.conflicts) == 1, "conflict was not reported")
    _require(
        conflict_resolution.conflicts[0].winner == "second",
        "load-order winner was not the last enabled mod",
    )
    engine.apply(conflict_resolution)
    _require(shared.read_bytes() == b"second-shared", "conflict winner was not applied")
    _require(first_only.read_bytes() == b"first-only", "non-conflicting file changed")

    second_resolution = _resolution(Profile("Second", ["second"]), records)
    engine.apply(second_resolution)
    _require(shared.read_bytes() == b"second-shared", "second profile shared asset")
    _require(
        first_only.read_bytes() == b"vanilla-first-only",
        "disabled mod asset was not restored",
    )

    engine.apply(_resolution(Profile("Off", []), records))
    _require(shared.read_bytes() == b"vanilla-shared", "shared vanilla restoration")
    _require(
        first_only.read_bytes() == b"vanilla-first-only",
        "exclusive vanilla restoration",
    )

    engine.apply(first_resolution)
    shared.write_bytes(b"external-change")
    try:
        engine.apply(_resolution(Profile("Off", []), records))
    except ApplyError as exc:
        _require(
            "changed outside UMML Manager" in str(exc),
            "external change failed for an unexpected reason",
        )
    else:
        raise ValidationError("external change was overwritten without refusal")
    _require(
        shared.read_bytes() == b"external-change",
        "external change was not preserved",
    )


def _check_legacy_baseline_migration(root: Path) -> None:
    dat = root / "Persistent" / "dat"
    backup = root / "Persistent" / "dat.backup"
    target = dat / "cc" / "legacy"
    original = backup / "cc" / "legacy"
    target.parent.mkdir(parents=True)
    original.parent.mkdir(parents=True)
    target.write_bytes(b"legacy-mod")
    original.write_bytes(b"vanilla-original")

    prepared = root / "prepared"
    source = prepared / "cc" / "legacy"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"legacy-mod")
    record = _prepared_record(
        "legacy",
        "Legacy",
        prepared,
        {"cc/legacy": source},
    )
    resolution = _resolution(Profile("Legacy", ["legacy"]), [record])
    store = ManagerStore(root / "manager")
    store.save_mod(record)
    store.save_settings({"dat_path": str(dat)})
    engine = ApplyEngine(store, dat, process_check=lambda _game: ())

    try:
        engine.apply(resolution)
    except LegacyBaselineMigrationRequired as exc:
        _require(exc.can_import, "complete legacy backup was not importable")
    else:
        raise ValidationError("legacy takeover did not require explicit migration")

    applied = engine.apply(resolution, import_legacy_baselines=True)
    _require(applied.imported_baselines == 1, "legacy baseline was not imported")
    _require(target.read_bytes() == b"legacy-mod", "legacy mod changed during adoption")
    _require(
        original.read_bytes() == b"vanilla-original",
        "legacy backup was moved or changed",
    )
    engine.apply(_resolution(Profile("Off", []), [record]))
    _require(
        target.read_bytes() == b"vanilla-original",
        "imported legacy original was not restored",
    )


def _check_interrupted_recovery(root: Path) -> None:
    dat = root / "dat"
    target = dat / "dd" / "recover"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"partially-applied")
    store = ManagerStore(root / "manager")
    store.save_settings({"dat_path": str(dat)})
    engine = ApplyEngine(store, dat, process_check=lambda _game: ())
    transaction = (
        store.paths.transactions
        / f"apply-{engine.target_id}-self-test-interrupted"
    )
    snapshot = transaction / "snapshots" / "dd" / "recover"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b"before-apply")
    atomic_write_json(
        transaction / "journal.json",
        {
            "version": JOURNAL_VERSION,
            "transaction_id": transaction.name,
            "target_id": engine.target_id,
            "dat_path": str(dat.resolve()),
            "phase": "applying",
            "manifest": {
                "dd/recover": {
                    "existed": True,
                    "sha256": hash_file(snapshot),
                }
            },
        },
    )

    result = engine.apply(_resolution(Profile("Off", []), []))
    _require(result.recovered_transactions == 1, "transaction was not recovered")
    _require(target.read_bytes() == b"before-apply", "snapshot was not restored")
    _require(not transaction.exists(), "recovered transaction was not cleaned")


def _prepared_record(
    mod_id: str,
    name: str,
    prepared_root: Path,
    files: dict[str, Path],
) -> ModRecord:
    return ModRecord(
        mod_id,
        name,
        version="1",
        regions=["global"],
        prepared_path=str(prepared_root),
        files={relative: hash_file(path) for relative, path in files.items()},
        prepared_against=SELF_TEST_FINGERPRINT,
    )


def _resolution(profile: Profile, records: list[ModRecord]):
    resolution = resolve_profile(
        Profile(
            profile.name,
            list(profile.enabled),
            region="global",
            installation_key=SELF_TEST_INSTALLATION,
        ),
        records,
        target_region="global",
        target_installation_key=SELF_TEST_INSTALLATION,
        metadata_fingerprint=SELF_TEST_FINGERPRINT,
    )
    if resolution.blocking_issues:
        raise ValidationError(
            "self-test profile unexpectedly has blockers: "
            + "; ".join(resolution.blocking_issues)
        )
    return resolution


def _file_state(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, ""
    if not path.is_file():
        raise ValidationError(f"Managed target is not a regular file: {path}")
    return True, hash_file(path)


def _copy_stable_optional(source: Path, target: Path) -> int:
    before_exists, before_hash = _file_state(source)
    if not before_exists:
        return 0
    size = source.stat().st_size
    atomic_copy_file(source, target)
    after_exists, after_hash = _file_state(source)
    if not after_exists or after_hash != before_hash:
        raise ValidationError(
            f"Source changed while creating the disposable copy: {source}"
        )
    if hash_file(target) != before_hash:
        raise ValidationError(
            f"Disposable copy verification failed: {source}"
        )
    return size


def _copy_trusted_baseline(
    source_store: ManagerStore,
    target_store: ManagerStore,
    relative: str,
) -> None:
    source = path_under(source_store.paths.baseline, relative)
    source_marker = source.with_name(source.name + ".umml-missing")
    source_digest = source.with_name(source.name + ".umml-sha256")
    target = path_under(target_store.paths.baseline, relative)
    target_marker = target.with_name(target.name + ".umml-missing")
    target_digest = target.with_name(target.name + ".umml-sha256")

    present = tuple(
        path.is_file()
        for path in (source, source_marker, source_digest)
    )
    if not any(present):
        return
    if source.is_file():
        if source_marker.exists():
            raise ValidationError(
                f"Baseline file and missing marker both exist for {relative}"
            )
        actual = hash_file(source)
        if source_digest.is_file():
            try:
                document = json.loads(
                    source_digest.read_text(encoding="utf-8")
                )
                expected = validate_sha256(str(document.get("sha256", "")))
            except (
                OSError,
                json.JSONDecodeError,
                AttributeError,
                SafetyError,
                ValueError,
            ) as exc:
                raise ValidationError(
                    f"Baseline integrity record is unreadable for {relative}"
                ) from exc
            if expected != actual:
                raise ValidationError(
                    f"Baseline integrity mismatch for {relative}"
                )
        atomic_copy_file(source, target)
        atomic_write_json(
            target_digest,
            {
                "version": BASELINE_VERSION,
                "sha256": actual,
                "origin": "disposable-profile-verification",
            },
        )
        return
    if source_marker.is_file():
        try:
            marker = json.loads(source_marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(
                f"Missing-file baseline marker is unreadable for {relative}"
            ) from exc
        if not isinstance(marker, dict) or marker.get("missing") is not True:
            raise ValidationError(
                f"Missing-file baseline marker is invalid for {relative}"
            )
        atomic_write_json(
            target_marker,
            {
                "version": BASELINE_VERSION,
                "missing": True,
                "origin": "disposable-profile-verification",
            },
        )
        return
    raise ValidationError(
        f"Baseline metadata is incomplete for {relative}"
    )


def _validate_real_baseline_scope(
    store: ManagerStore,
    *,
    target_id: str,
    dat: Path,
) -> None:
    root = store.paths.baseline
    if not root.is_dir():
        return
    manifest = root / ".umml-target.json"
    has_entries = any(
        path.name != manifest.name
        for path in root.rglob("*")
    )
    if not manifest.is_file():
        if not has_entries:
            return
        saved = str(
            store.load_settings(repair=False).get("dat_path", "")
        ).strip()
        try:
            matches = bool(
                saved
                and Path(saved).expanduser().resolve() == dat.resolve()
            )
        except OSError:
            matches = False
        if matches:
            return
        raise ValidationError(
            "Existing Manager baseline has no target identity and does not "
            "match the saved game data path"
        )
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(
            f"Baseline target manifest is unreadable: {manifest}"
        ) from exc
    if not isinstance(document, dict):
        raise ValidationError(
            f"Baseline target manifest has an invalid format: {manifest}"
        )
    try:
        version = int(document.get("version", 1))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Baseline target manifest has an invalid version") from exc
    if version < 1 or version > BASELINE_VERSION:
        raise ValidationError(
            f"Unsupported baseline target manifest version: {version}"
        )
    if document.get("target_id") != target_id:
        raise ValidationError(
            "Manager baseline belongs to another game installation"
        )


def _assert_matches_isolated_baseline(
    store: ManagerStore,
    dat: Path,
    relative: str,
) -> None:
    baseline = path_under(store.paths.baseline, relative)
    marker = baseline.with_name(baseline.name + ".umml-missing")
    target = path_under(dat, relative)
    if baseline.is_file():
        if not target.is_file() or hash_file(target) != hash_file(baseline):
            raise ValidationError(
                f"Disposable restore did not match baseline: {relative}"
            )
        return
    if marker.is_file():
        if target.exists():
            raise ValidationError(
                f"Disposable restore did not remove add-only path: {relative}"
            )
        return
    raise ValidationError(
        f"Disposable restore produced no baseline for {relative}"
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)

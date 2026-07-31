from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .locking import FileLock, LockError
from .process import running_game_processes
from .resolver import Resolution
from .safety import (
    SafetyError,
    atomic_copy_file,
    atomic_write_json,
    hash_file,
    normalize_relative_path,
    path_under,
    validate_sha256,
)
from .store import ManagerStore

ACTIVE_VERSION = 2
JOURNAL_VERSION = 2
BASELINE_VERSION = 1


class ApplyError(RuntimeError):
    pass


class LegacyBaselineMigrationRequired(ApplyError):
    """Raised when legacy-managed files need an explicit vanilla baseline."""

    def __init__(
        self,
        paths: list[str],
        *,
        backup_root: Path,
        importable: list[str],
        problems: dict[str, str],
    ):
        self.paths = tuple(paths)
        self.backup_root = backup_root
        self.importable = tuple(importable)
        self.problems = dict(problems)
        count = len(self.paths)
        noun = "file" if count == 1 else "files"
        message = (
            f"{count} current game {noun} need original copies before UMML Manager "
            "can take over safely. UMML Manager has no vanilla baseline for them. "
            "Import the legacy originals or restore the game files before applying."
        )
        super().__init__(message)

    @property
    def can_import(self) -> bool:
        return bool(self.paths) and len(self.importable) == len(self.paths)


@dataclass(frozen=True)
class ApplyResult:
    installed: int
    restored: int
    unchanged: int
    recovered_transactions: int = 0
    imported_baselines: int = 0


class ApplyEngine:
    def __init__(
        self,
        store: ManagerStore,
        dat_path: str | Path,
        *,
        game_dir: str | Path | None = None,
        process_check: Callable[[str | Path | None], tuple] = running_game_processes,
    ):
        self.store = store
        self.dat_path = Path(dat_path).expanduser()
        self.game_dir = game_dir
        self.process_check = process_check
        self.target_id = _target_id(self.dat_path)

    def apply(
        self,
        resolution: Resolution,
        *,
        force: bool = False,
        import_legacy_baselines: bool = False,
    ) -> ApplyResult:
        self._validate_resolution(resolution)
        if not self.dat_path.is_dir():
            raise ApplyError(f"Game dat directory not found: {self.dat_path}")
        try:
            with FileLock(
                self.store.paths.locks / f"deployment-{self.target_id}.lock",
                purpose="applying or recovering a profile",
            ):
                self._assert_game_closed()
                recovered = self._recover_incomplete_transactions()
                self._assert_game_closed()
                self._ensure_baseline_scope()
                active_document = self._read_active_document()
                active = dict(active_document["files"])
                desired = resolution.winners
                affected = sorted(set(active) | set(desired))
                self._validate_sources(desired)
                self._check_external_changes(active, affected, force)
                return self._apply_transaction(
                    resolution,
                    active_document,
                    active,
                    affected,
                    recovered,
                    force=force,
                    import_legacy_baselines=import_legacy_baselines,
                )
        except LockError as exc:
            raise ApplyError(str(exc)) from exc
        except SafetyError as exc:
            raise ApplyError(str(exc)) from exc

    def _validate_resolution(self, resolution: Resolution) -> None:
        groups = (
            ("Missing mods", resolution.missing),
            ("Unprepared mods", resolution.unprepared),
            ("Unsupported packages", resolution.unsupported),
            ("Region incompatibilities", resolution.incompatible),
            ("Invalid manifests", resolution.invalid),
            ("Missing dependencies", resolution.missing_dependencies),
            ("Declared incompatibilities", resolution.incompatibility_conflicts),
        )
        problems = [
            f"{label}: {', '.join(values)}"
            for label, values in groups
            if values
        ]
        if problems:
            raise ApplyError("Profile cannot be applied.\n" + "\n".join(problems))

    def _assert_game_closed(self) -> None:
        running = self.process_check(self.game_dir)
        if running:
            names = ", ".join(
                sorted({getattr(item, "name", "game") for item in running})
            )
            raise ApplyError(
                f"Game is running ({names}); close it before applying changes"
            )

    def _validate_sources(self, desired: dict) -> None:
        failures: list[str] = []
        for relative, claim in desired.items():
            source = path_under(claim.source_path, relative)
            if not source.is_file():
                failures.append(f"{claim.mod_id}: missing {relative}")
                continue
            actual = hash_file(source)
            if actual != claim.sha256:
                failures.append(
                    f"{claim.mod_id}: prepared hash changed for {relative} "
                    f"(expected {claim.sha256}, found {actual})"
                )
        if failures:
            raise ApplyError(
                "Prepared cache verification failed. Re-prepare the affected mods.\n"
                + "\n".join(failures[:20])
            )

    def _apply_transaction(
        self,
        resolution: Resolution,
        active_document: dict,
        active: dict,
        affected: list[str],
        recovered: int,
        *,
        force: bool,
        import_legacy_baselines: bool,
    ) -> ApplyResult:
        self.store.paths.transactions.mkdir(parents=True, exist_ok=True)
        transaction = Path(
            tempfile.mkdtemp(
                prefix=f"apply-{self.target_id}-",
                dir=self.store.paths.transactions,
            )
        )
        transaction_id = transaction.name
        snapshots = transaction / "snapshots"
        snapshots.mkdir(parents=True, exist_ok=True)
        journal_path = transaction / "journal.json"
        manifest: dict[str, dict[str, object]] = {}
        active_written = False
        mutation_started = False
        atomic_write_json(
            journal_path,
            self._journal(transaction_id, "snapshotting", manifest),
        )
        try:
            for relative in affected:
                target = path_under(self.dat_path, relative)
                snapshot = path_under(snapshots, relative)
                if target.exists() and not target.is_file():
                    raise ApplyError(f"Managed target is not a regular file: {target}")
                existed = target.is_file()
                entry: dict[str, object] = {"existed": existed, "sha256": ""}
                if existed:
                    atomic_copy_file(target, snapshot)
                    entry["sha256"] = hash_file(snapshot)
                manifest[relative] = entry
            atomic_write_json(
                journal_path,
                self._journal(transaction_id, "applying", manifest),
            )
            imported_baselines = self._prepare_first_baselines(
                resolution,
                active,
                manifest,
                import_legacy_baselines=import_legacy_baselines,
            )
            self._assert_game_closed()
            self._validate_snapshot_state(
                active,
                manifest,
                force=force,
            )
            mutation_started = True

            installed = restored = unchanged = 0
            new_active: dict[str, dict[str, str]] = {}
            for relative in affected:
                target = path_under(self.dat_path, relative)
                claim = resolution.winners.get(relative)
                if claim is None:
                    if self._restore_baseline(relative, target):
                        restored += 1
                    continue
                source = path_under(claim.source_path, relative)
                if target.is_file() and hash_file(target) == claim.sha256:
                    if relative not in active:
                        self._require_existing_baseline_for_adoption(
                            relative,
                            target,
                        )
                    unchanged += 1
                else:
                    if relative in imported_baselines:
                        self._require_existing_baseline_for_adoption(
                            relative,
                            target,
                        )
                    else:
                        self._capture_baseline(
                            relative,
                            target,
                            active.get(relative),
                        )
                    atomic_copy_file(source, target)
                    installed_hash = hash_file(target)
                    if installed_hash != claim.sha256:
                        raise ApplyError(
                            f"Installed asset verification failed for {relative}: "
                            f"expected {claim.sha256}, found {installed_hash}"
                        )
                    installed += 1
                new_active[relative] = {
                    "owner": claim.mod_id,
                    "version": claim.mod_version,
                    "sha256": claim.sha256,
                    "profile": resolution.profile,
                }

            self._write_active(new_active, transaction_id=transaction_id)
            active_written = True
            atomic_write_json(
                journal_path,
                self._journal(transaction_id, "committed", manifest),
            )
            shutil.rmtree(transaction, ignore_errors=True)
            return ApplyResult(
                installed=installed,
                restored=restored,
                unchanged=unchanged,
                recovered_transactions=recovered,
                imported_baselines=len(imported_baselines),
            )
        except Exception as exc:
            if not mutation_started:
                shutil.rmtree(transaction, ignore_errors=True)
                if isinstance(exc, ApplyError):
                    raise
                raise ApplyError(f"Apply failed before game-file mutation: {exc}") from exc

            rollback_error: Exception | None = None
            try:
                self._rollback(snapshots, manifest)
                if active_written:
                    self._write_active_document(active_document)
            except Exception as recovery_exc:
                rollback_error = recovery_exc
            if rollback_error is None:
                shutil.rmtree(transaction, ignore_errors=True)
            if rollback_error is not None:
                raise ApplyError(
                    "Apply failed and automatic rollback also failed. Preserve this recovery "
                    f"directory and do not apply another profile: {transaction}\n"
                    f"Apply error: {exc}\nRollback error: {rollback_error}"
                ) from exc
            if isinstance(exc, ApplyError):
                raise
            raise ApplyError(f"Apply failed and was rolled back: {exc}") from exc

    def _require_existing_baseline_for_adoption(
        self,
        relative: str,
        target: Path,
    ) -> None:
        baseline, marker, digest = self._baseline_paths(relative)
        if not (baseline.exists() or marker.exists() or digest.exists()):
            raise ApplyError(
                f"The current game file for {relative} already matches the requested "
                "mod, but UMML Manager has no vanilla baseline for it. The file cannot "
                "be adopted safely. Restore the original game file before applying, or "
                "use an explicit recovery workflow."
            )
        if baseline.is_file():
            self._verify_baseline_file(baseline, digest, relative)
            return
        if marker.is_file():
            self._validate_missing_marker(marker, relative)
            return
        raise ApplyError(
            f"Vanilla baseline metadata is incomplete for {relative}. "
            "Do not deploy until the baseline is inspected."
        )

    def _prepare_first_baselines(
        self,
        resolution: Resolution,
        active: dict,
        manifest: dict[str, dict[str, object]],
        *,
        import_legacy_baselines: bool,
    ) -> set[str]:
        unbaselined: dict[str, tuple[bool, str, str]] = {}
        for relative, claim in resolution.winners.items():
            if relative in active:
                continue
            entry = manifest.get(relative)
            if entry is None:
                raise ApplyError(
                    f"Transaction snapshot metadata is missing for {relative}"
                )
            existed, snapshot_hash = self._snapshot_entry(entry, relative)
            baseline, marker, digest = self._baseline_paths(relative)
            if baseline.exists() or marker.exists() or digest.exists():
                if existed and snapshot_hash == claim.sha256:
                    self._require_existing_baseline_for_adoption(
                        relative,
                        path_under(self.dat_path, relative),
                    )
                continue
            unbaselined[relative] = (
                existed,
                snapshot_hash,
                claim.sha256,
            )

        if not unbaselined:
            return set()

        available, unavailable = self._legacy_baseline_candidates(
            list(unbaselined),
        )
        required: list[str] = []
        candidates: dict[str, tuple[Path, str]] = {}
        problems: dict[str, str] = {}
        for relative, (
            existed,
            snapshot_hash,
            requested_hash,
        ) in unbaselined.items():
            candidate = available.get(relative)
            known_hashes = resolution.known_mod_hashes.get(
                relative,
                (requested_hash,),
            )
            matches_known_mod = existed and snapshot_hash in known_hashes
            if candidate is not None:
                _source, backup_hash = candidate
                matches_current = existed and backup_hash == snapshot_hash
                if matches_current and not matches_known_mod:
                    continue
                required.append(relative)
                candidates[relative] = candidate
                continue
            if matches_known_mod:
                required.append(relative)
                problems[relative] = unavailable.get(
                    relative,
                    "original backup is unavailable",
                )

        if not required:
            return set()
        if problems or not import_legacy_baselines:
            raise LegacyBaselineMigrationRequired(
                required,
                backup_root=self.legacy_backup_root,
                importable=sorted(candidates),
                problems=problems,
            )

        self._import_legacy_baselines(candidates)
        for relative in required:
            self._require_existing_baseline_for_adoption(
                relative,
                path_under(self.dat_path, relative),
            )
        return set(candidates)

    @property
    def legacy_backup_root(self) -> Path:
        return self.dat_path.parent / "dat.backup"

    def _legacy_baseline_candidates(
        self,
        relatives: list[str],
    ) -> tuple[dict[str, tuple[Path, str]], dict[str, str]]:
        candidates: dict[str, tuple[Path, str]] = {}
        problems: dict[str, str] = {}
        if self.legacy_backup_root.is_symlink():
            return {}, {
                relative: "legacy backup folder is a symbolic link"
                for relative in relatives
            }
        for relative in sorted(relatives):
            try:
                source = path_under(self.legacy_backup_root, relative)
            except SafetyError as exc:
                problems[relative] = str(exc)
                continue
            if not source.is_file():
                problems[relative] = "original backup is missing"
                continue
            target = path_under(self.dat_path, relative)
            if target.is_file():
                try:
                    if source.samefile(target):
                        problems[relative] = (
                            "backup and current game file are the same filesystem object"
                        )
                        continue
                except OSError as exc:
                    problems[relative] = (
                        f"could not compare backup with current game file: {exc}"
                    )
                    continue
            try:
                source_hash = hash_file(source)
            except OSError as exc:
                problems[relative] = f"original backup is unreadable: {exc}"
                continue
            candidates[relative] = (source, source_hash)
        return candidates, problems

    def _import_legacy_baselines(
        self,
        candidates: dict[str, tuple[Path, str]],
    ) -> None:
        created: list[tuple[Path, Path]] = []
        try:
            for relative, (source, expected) in sorted(candidates.items()):
                baseline, marker, digest = self._baseline_paths(relative)
                if baseline.exists() or marker.exists() or digest.exists():
                    raise ApplyError(
                        f"Vanilla baseline metadata appeared while importing {relative}. "
                        "No existing baseline was replaced."
                    )
                atomic_copy_file(source, baseline)
                created.append((baseline, digest))
                actual = hash_file(baseline)
                if actual != expected:
                    raise ApplyError(
                        f"Legacy backup changed while importing {relative}. "
                        "No game files were changed."
                    )
                atomic_write_json(
                    digest,
                    {
                        "version": BASELINE_VERSION,
                        "sha256": actual,
                        "origin": "legacy-dat.backup",
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
        except Exception:
            for baseline, digest in reversed(created):
                digest.unlink(missing_ok=True)
                baseline.unlink(missing_ok=True)
            raise

    def _baseline_paths(self, relative: str) -> tuple[Path, Path, Path]:
        baseline = path_under(self.store.paths.baseline, relative)
        marker = baseline.with_name(baseline.name + ".umml-missing")
        digest = baseline.with_name(baseline.name + ".umml-sha256")
        return baseline, marker, digest

    def _capture_baseline(
        self,
        relative: str,
        target: Path,
        active_record: object,
    ) -> None:
        baseline, marker, digest = self._baseline_paths(relative)
        if baseline.exists() or marker.exists() or digest.exists():
            if baseline.is_file():
                baseline_hash = self._verify_baseline_file(
                    baseline,
                    digest,
                    relative,
                )
                if active_record:
                    return
                if target.is_file() and hash_file(target) == baseline_hash:
                    return
                raise ApplyError(
                    f"The vanilla baseline for {relative} no longer matches the game. "
                    "A game update or another tool changed this path. Baseline refresh "
                    "must be explicit."
                )
            if marker.is_file():
                self._validate_missing_marker(marker, relative)
                if active_record or not target.exists():
                    return
                raise ApplyError(
                    f"The vanilla baseline records {relative} as absent, but the game now "
                    "contains that path. Baseline refresh must be explicit."
                )
            raise ApplyError(
                f"Vanilla baseline metadata is incomplete for {relative}. "
                "Do not deploy until the baseline is inspected."
            )

        baseline.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            atomic_copy_file(target, baseline)
            baseline_hash = hash_file(baseline)
            atomic_write_json(
                digest,
                {
                    "version": BASELINE_VERSION,
                    "sha256": baseline_hash,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        elif target.exists():
            raise ApplyError(f"Cannot capture a non-file baseline: {target}")
        else:
            atomic_write_json(
                marker,
                {
                    "version": BASELINE_VERSION,
                    "missing": True,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                },
            )

    def _restore_baseline(self, relative: str, target: Path) -> bool:
        baseline, marker, digest = self._baseline_paths(relative)
        if baseline.is_file():
            expected = self._verify_baseline_file(baseline, digest, relative)
            atomic_copy_file(baseline, target)
            restored_hash = hash_file(target)
            if restored_hash != expected:
                raise ApplyError(
                    f"Restored baseline verification failed for {relative}: "
                    f"expected {expected}, found {restored_hash}"
                )
            return True
        if marker.is_file():
            self._validate_missing_marker(marker, relative)
            if target.exists() and not target.is_file():
                raise ApplyError(f"Cannot remove non-file managed target: {target}")
            existed = target.exists()
            target.unlink(missing_ok=True)
            return existed
        raise ApplyError(
            f"No vanilla baseline exists for previously managed path {relative}. "
            "The active state was preserved and no further files were changed."
        )

    def _verify_baseline_file(
        self,
        baseline: Path,
        digest_path: Path,
        relative: str,
    ) -> str:
        if not digest_path.is_file():
            if not self._saved_dat_matches():
                raise ApplyError(
                    f"Legacy baseline for {relative} has no integrity record and the saved "
                    "installation does not match the current target."
                )
            migrated_hash = hash_file(baseline)
            atomic_write_json(
                digest_path,
                {
                    "version": BASELINE_VERSION,
                    "sha256": migrated_hash,
                    "migrated_from_legacy": True,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            return migrated_hash
        try:
            data = json.loads(digest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApplyError(
                f"Baseline integrity record is unreadable for {relative}: {digest_path}"
            ) from exc
        if not isinstance(data, dict):
            raise ApplyError(
                f"Baseline integrity record has an invalid format for {relative}"
            )
        version = _document_version(data, BASELINE_VERSION, "baseline integrity record")
        if version < 1:
            raise ApplyError(f"Unsupported baseline integrity version for {relative}")
        try:
            expected = validate_sha256(str(data.get("sha256", "")))
        except SafetyError as exc:
            raise ApplyError(
                f"Baseline integrity record has an invalid SHA-256 for {relative}"
            ) from exc
        actual = hash_file(baseline)
        if actual != expected:
            raise ApplyError(
                f"Vanilla baseline was changed for {relative}: expected {expected}, found {actual}"
            )
        return expected

    @staticmethod
    def _validate_missing_marker(marker: Path, relative: str) -> None:
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApplyError(
                f"Missing-file baseline marker is unreadable for {relative}: {marker}"
            ) from exc
        if not isinstance(data, dict) or data.get("missing") is not True:
            raise ApplyError(
                f"Missing-file baseline marker has an invalid format for {relative}"
            )
        _document_version(data, BASELINE_VERSION, "missing-file baseline marker")

    def _check_external_changes(
        self,
        active: dict,
        affected: list[str],
        force: bool,
    ) -> None:
        if force:
            return
        conflicts: list[str] = []
        for relative in affected:
            record = active.get(relative)
            if not isinstance(record, dict):
                continue
            target = path_under(self.dat_path, relative)
            expected = str(record["sha256"])
            if not target.is_file() or hash_file(target) != expected:
                conflicts.append(relative)
        if conflicts:
            sample = ", ".join(conflicts[:5])
            raise ApplyError(
                f"{len(conflicts)} active asset(s) changed outside UMML Manager "
                f"({sample}). Refusing to overwrite them without --force."
            )

    def _validate_snapshot_state(
        self,
        active: dict,
        manifest: dict[str, dict[str, object]],
        *,
        force: bool,
    ) -> None:
        if not force:
            stale_active: list[str] = []
            for relative, record in active.items():
                entry = manifest.get(relative)
                if not isinstance(record, dict) or entry is None:
                    continue
                existed, snapshot_hash = self._snapshot_entry(entry, relative)
                if not existed or snapshot_hash != str(record["sha256"]):
                    stale_active.append(relative)
            if stale_active:
                sample = ", ".join(stale_active[:5])
                raise ApplyError(
                    f"{len(stale_active)} active asset(s) changed while UMML Manager "
                    f"was preparing the transaction ({sample}). Refusing to overwrite "
                    "them without --force."
                )

        changed_after_snapshot: list[str] = []
        for relative, entry in manifest.items():
            existed, snapshot_hash = self._snapshot_entry(entry, relative)
            target = path_under(self.dat_path, relative)
            try:
                matches = (
                    target.is_file() and hash_file(target) == snapshot_hash
                    if existed
                    else not target.exists()
                )
            except OSError:
                matches = False
            if not matches:
                changed_after_snapshot.append(relative)
        if changed_after_snapshot:
            sample = ", ".join(changed_after_snapshot[:5])
            raise ApplyError(
                f"{len(changed_after_snapshot)} target asset(s) changed after UMML "
                f"Manager captured its recovery snapshots ({sample}). No game files "
                "were changed; retry after the target is stable."
            )

    def _rollback(self, snapshots: Path, manifest: dict) -> None:
        failures: list[str] = []
        for relative, raw_entry in manifest.items():
            try:
                canonical = normalize_relative_path(str(relative))
                existed, expected = self._snapshot_entry(raw_entry, canonical)
                target = path_under(self.dat_path, canonical)
                snapshot = path_under(snapshots, canonical)
                if existed:
                    if not snapshot.is_file():
                        raise ApplyError(f"Recovery snapshot is missing: {snapshot}")
                    if expected:
                        actual_snapshot = hash_file(snapshot)
                        if actual_snapshot != expected:
                            raise ApplyError(
                                f"Recovery snapshot hash mismatch for {canonical}: "
                                f"expected {expected}, found {actual_snapshot}"
                            )
                    atomic_copy_file(snapshot, target)
                    if expected and hash_file(target) != expected:
                        raise ApplyError(
                            f"Recovery target verification failed for {canonical}"
                        )
                else:
                    if target.exists() and not target.is_file():
                        raise ApplyError(f"Recovery target is not a file: {target}")
                    target.unlink(missing_ok=True)
            except Exception as exc:
                failures.append(f"{relative}: {exc}")
        if failures:
            raise ApplyError(
                "Rollback could not restore every path:\n"
                + "\n".join(failures[:20])
            )

    def _recover_incomplete_transactions(self) -> int:
        root = self.store.paths.transactions
        if not root.is_dir():
            return 0
        recovered = 0
        for transaction in sorted(root.glob(f"apply-{self.target_id}-*")):
            if not transaction.is_dir():
                continue
            journal_path = transaction / "journal.json"
            try:
                journal = json.loads(journal_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ApplyError(
                    f"Incomplete deployment has an unreadable journal: {transaction}. "
                    "Do not delete it until its snapshots are inspected."
                ) from exc
            if not isinstance(journal, dict) or journal.get("target_id") != self.target_id:
                raise ApplyError(f"Invalid deployment journal: {journal_path}")
            _document_version(journal, JOURNAL_VERSION, "deployment journal")
            phase = str(journal.get("phase", ""))
            manifest = journal.get("manifest", {})
            if not isinstance(manifest, dict):
                raise ApplyError(
                    f"Invalid deployment snapshot manifest: {journal_path}"
                )

            # Snapshot setup cannot have modified the game. Clean it before
            # active-state migration, even if an old state document is present.
            if phase == "snapshotting":
                shutil.rmtree(transaction, ignore_errors=True)
                recovered += 1
                continue

            normalized_manifest = self._validate_snapshot_manifest(
                manifest,
                journal_path,
            )
            active_document = self._read_active_document(allow_legacy=False)
            if active_document.get("transaction_id") == transaction.name:
                shutil.rmtree(transaction, ignore_errors=True)
                recovered += 1
                continue
            if phase in {"applying", "committed"}:
                self._assert_game_closed()
                self._rollback(transaction / "snapshots", normalized_manifest)
                shutil.rmtree(transaction, ignore_errors=True)
                recovered += 1
                continue
            raise ApplyError(
                f"Unknown deployment journal phase {phase!r}: {journal_path}"
            )
        return recovered

    def _validate_snapshot_manifest(
        self,
        manifest: dict,
        journal_path: Path,
    ) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        for relative, raw_entry in manifest.items():
            try:
                canonical = normalize_relative_path(str(relative))
            except SafetyError as exc:
                raise ApplyError(
                    f"Unsafe path in deployment journal {journal_path}: {relative!r}"
                ) from exc
            if canonical in result:
                raise ApplyError(
                    f"Duplicate path in deployment journal {journal_path}: {canonical}"
                )
            existed, sha256 = self._snapshot_entry(raw_entry, canonical)
            result[canonical] = {"existed": existed, "sha256": sha256}
        return result

    @staticmethod
    def _snapshot_entry(raw_entry: object, relative: str) -> tuple[bool, str]:
        if isinstance(raw_entry, bool):
            return raw_entry, ""
        if not isinstance(raw_entry, dict):
            raise ApplyError(f"Invalid recovery snapshot entry for {relative}")
        existed = raw_entry.get("existed")
        if not isinstance(existed, bool):
            raise ApplyError(
                f"Recovery snapshot entry has no boolean existed flag for {relative}"
            )
        raw_hash = str(raw_entry.get("sha256", ""))
        if existed:
            try:
                return True, validate_sha256(raw_hash)
            except SafetyError as exc:
                raise ApplyError(
                    f"Recovery snapshot entry has an invalid SHA-256 for {relative}"
                ) from exc
        if raw_hash:
            raise ApplyError(
                f"Recovery snapshot for absent path {relative} unexpectedly has a hash"
            )
        return False, ""

    def _read_active_document(self, *, allow_legacy: bool = True) -> dict:
        path = self.store.paths.state
        if not path.is_file():
            return {
                "version": ACTIVE_VERSION,
                "target_id": self.target_id,
                "dat_path": str(self.dat_path.resolve()),
                "files": {},
            }
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApplyError(
                f"UMML Manager's active deployment state is unreadable: {path}. "
                "No game files were changed. Restore or inspect this file before retrying."
            ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
            raise ApplyError(
                f"UMML Manager's active deployment state has an invalid format: {path}. "
                "No game files were changed."
            )
        _document_version(data, ACTIVE_VERSION, "active deployment state")
        recorded_target = str(data.get("target_id", ""))
        if recorded_target and recorded_target != self.target_id:
            raise ApplyError(
                "The active deployment state belongs to another game installation. "
                f"Recorded target {recorded_target}; current target {self.target_id}."
            )
        if not recorded_target and data["files"]:
            if not allow_legacy or not self._saved_dat_matches():
                raise ApplyError(
                    "Legacy deployment state has no installation identity. Open the "
                    "installation saved when it was created before migrating or recovering it."
                )
            data["target_id"] = self.target_id
            data["dat_path"] = str(self.dat_path.resolve())
        data["files"] = self._validate_active_files(data["files"], path)
        return data

    @staticmethod
    def _validate_active_files(files: dict, state_path: Path) -> dict:
        validated: dict[str, dict[str, str]] = {}
        for relative, raw_record in files.items():
            try:
                canonical = normalize_relative_path(str(relative))
            except SafetyError as exc:
                raise ApplyError(
                    f"Unsafe managed path in active state {state_path}: {relative!r}"
                ) from exc
            if canonical in validated:
                raise ApplyError(
                    f"Duplicate managed path in active state {state_path}: {canonical}"
                )
            if not isinstance(raw_record, dict):
                raise ApplyError(
                    f"Invalid active record for {canonical} in {state_path}"
                )
            try:
                sha256 = validate_sha256(str(raw_record.get("sha256", "")))
            except SafetyError as exc:
                raise ApplyError(
                    f"Invalid active SHA-256 for {canonical} in {state_path}"
                ) from exc
            validated[canonical] = {
                "owner": str(raw_record.get("owner", "")),
                "version": str(raw_record.get("version", "")),
                "sha256": sha256,
                "profile": str(raw_record.get("profile", "")),
            }
        return validated

    def _write_active(self, files: dict, *, transaction_id: str) -> None:
        self._write_active_document(
            {
                "version": ACTIVE_VERSION,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "target_id": self.target_id,
                "dat_path": str(self.dat_path.resolve()),
                "transaction_id": transaction_id,
                "files": files,
            }
        )

    def _write_active_document(self, data: dict) -> None:
        atomic_write_json(self.store.paths.state, data)

    def _ensure_baseline_scope(self) -> None:
        manifest = self.store.paths.baseline / ".umml-target.json"
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ApplyError(
                    f"Baseline target manifest is unreadable: {manifest}"
                ) from exc
            if not isinstance(data, dict):
                raise ApplyError(
                    f"Baseline target manifest has an invalid format: {manifest}"
                )
            _document_version(data, BASELINE_VERSION, "baseline target manifest")
            if data.get("target_id") != self.target_id:
                raise ApplyError(
                    "The vanilla baseline belongs to another game installation. "
                    "Do not reuse it across Global/Japan or different Steam libraries."
                )
            return
        has_baseline = self.store.paths.baseline.is_dir() and any(
            path.name != manifest.name
            for path in self.store.paths.baseline.rglob("*")
        )
        if has_baseline and not self._saved_dat_matches():
            raise ApplyError(
                "Legacy vanilla baseline has no installation identity and the saved game "
                "path does not match the current target."
            )
        atomic_write_json(
            manifest,
            {
                "version": BASELINE_VERSION,
                "target_id": self.target_id,
                "dat_path": str(self.dat_path.resolve()),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _saved_dat_matches(self) -> bool:
        saved = str(self.store.load_settings().get("dat_path", ""))
        if not saved:
            return False
        try:
            return Path(saved).expanduser().resolve() == self.dat_path.resolve()
        except OSError:
            return False

    def _journal(
        self,
        transaction_id: str,
        phase: str,
        manifest: dict,
    ) -> dict:
        return {
            "version": JOURNAL_VERSION,
            "transaction_id": transaction_id,
            "target_id": self.target_id,
            "dat_path": str(self.dat_path.resolve()),
            "phase": phase,
            "manifest": dict(manifest),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def _document_version(data: dict, supported: int, label: str) -> int:
    try:
        version = int(data.get("version", 1))
    except (TypeError, ValueError) as exc:
        raise ApplyError(f"{label} has an invalid schema version") from exc
    if version < 1 or version > supported:
        raise ApplyError(
            f"{label} uses unsupported schema version {version}; supported up to {supported}"
        )
    return version


def _target_id(dat_path: Path) -> str:
    try:
        canonical = str(dat_path.resolve())
    except OSError:
        canonical = str(dat_path.absolute())
    return hashlib.sha256(
        canonical.encode("utf-8", errors="surrogateescape")
    ).hexdigest()[:20]

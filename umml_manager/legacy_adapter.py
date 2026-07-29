from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .locking import FileLock, LockError
from .models import PACKAGE_UMML_ASSETS, ModRecord
from .options import OptionError, select_source_paths
from .safety import SafetyError, atomic_copy_file, hash_file, validate_regular_tree
from .store import ManagerStore, StoreError


class _NullWidget:
    def __setitem__(self, key, value):
        return None

    def config(self, **kwargs):
        return None


class _NullRoot:
    def update_idletasks(self):
        return None


class LegacyAssetAdapter:
    """Reuse UMML's metadata lookup/encryption routine without its GUI."""

    def __init__(self, store: ManagerStore, meta_path: str | Path):
        self.store = store
        self.meta_path = Path(meta_path).expanduser()

    def prepare(self, record: ModRecord) -> ModRecord:
        if record.package_type != PACKAGE_UMML_ASSETS:
            raise StoreError(
                f"{record.name} is a {record.package_type} package and cannot be prepared "
                "by the legacy asset decoder."
            )
        source = Path(record.source_path)
        assets = source / "assets"
        if not assets.is_dir():
            raise StoreError(f"Missing assets folder: {assets}")
        if not self.meta_path.is_file():
            raise StoreError(f"Metadata database not found: {self.meta_path}")
        try:
            validate_regular_tree(assets)
        except SafetyError as exc:
            raise StoreError(str(exc)) from exc

        output = self.store.prepared_destination(record)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with FileLock(
                self.store.paths.locks / f"prepare-{record.id}.lock",
                purpose=f"preparing {record.id}",
            ):
                return self._prepare_locked(record, assets, output)
        except LockError as exc:
            raise StoreError(str(exc)) from exc

    def _prepare_locked(self, record: ModRecord, assets: Path, output: Path) -> ModRecord:
        stage_root = Path(
            tempfile.mkdtemp(prefix=f".{output.name}-prepare-", dir=output.parent)
        )
        decoded = stage_root / "decoded"
        normalized = stage_root / "normalized"
        decoded.mkdir()
        normalized.mkdir()
        backup = output.with_name(
            f".{output.name}.previous-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        )
        moved_old = False
        moved_new = False
        try:
            decoder = self._decoder()
            _decoded_count, missing = decoder.decrypt_assets_internal(
                str(assets),
                str(decoded),
                use_hash=False,
                filter_path=None,
            )
            try:
                validate_regular_tree(decoded)
            except SafetyError as exc:
                raise StoreError(f"Prepared output was unsafe: {exc}") from exc

            files: dict[str, str] = {}
            for path in sorted(item for item in decoded.rglob("*") if item.is_file()):
                name = path.name
                if len(name) < 2:
                    continue
                relative = (Path(name[:2]) / name).as_posix()
                destination = normalized / name[:2] / name
                if relative in files:
                    raise StoreError(
                        f"Preparation produced duplicate target hash {name}; existing cache was preserved."
                    )
                atomic_copy_file(path, destination)
                files[relative] = hash_file(destination)
            if not files:
                raise StoreError(
                    f"No compatible assets produced; {missing} entries were absent from metadata. "
                    "The previous prepared cache was preserved."
                )

            source_files = self._source_target_map(assets, files)
            if record.option_groups:
                mapped_targets = set(source_files.values())
                unmapped_targets = sorted(set(files) - mapped_targets)
                if unmapped_targets:
                    preview = ", ".join(unmapped_targets[:5])
                    raise StoreError(
                        "Configurable package preparation could not map every prepared "
                        f"asset back to its source path: {preview}. The previous cache "
                        "was preserved."
                    )
                try:
                    # This validates default selections, glob coverage, and rejects
                    # patterns that ambiguously control the same source asset.
                    select_source_paths(record.option_groups, {}, source_files)
                except OptionError as exc:
                    raise StoreError(f"Invalid configurable mod manifest: {exc}") from exc

            if output.exists():
                os.replace(output, backup)
                moved_old = True
            os.replace(normalized, output)
            moved_new = True
            updated = replace(
                record,
                prepared_path=str(output),
                files=files,
                source_files=source_files,
                prepared_against=hash_file(self.meta_path),
                prepared_at=datetime.now(timezone.utc).isoformat(),
            )
            try:
                self.store.save_mod(updated)
            except Exception:
                if moved_new and output.exists():
                    shutil.rmtree(output, ignore_errors=True)
                if moved_old and backup.exists():
                    os.replace(backup, output)
                raise
            shutil.rmtree(backup, ignore_errors=True)
            return updated
        finally:
            shutil.rmtree(stage_root, ignore_errors=True)
            if backup.exists() and not output.exists():
                os.replace(backup, output)

    def _source_target_map(
        self,
        assets: Path,
        prepared_files: dict[str, str],
    ) -> dict[str, str]:
        """Resolve creator-facing source paths to prepared hash paths.

        The legacy decoder intentionally returns only aggregate counts. The
        manager independently records this mapping so configuration remains a
        pure profile-resolution decision rather than filename mutation inside an
        immutable source directory.
        """

        mapping: dict[str, str] = {}
        owners: dict[str, str] = {}
        try:
            connection = sqlite3.connect(str(self.meta_path))
        except sqlite3.Error as exc:
            raise StoreError(f"Could not open metadata for source mapping: {exc}") from exc
        try:
            cursor = connection.cursor()
            cursor.execute("PRAGMA table_info(a)")
            columns = {str(row[1]) for row in cursor.fetchall()}
            if "n" not in columns or "h" not in columns:
                raise StoreError("Metadata table a is missing source-name/hash columns")

            for source in sorted(item for item in assets.rglob("*") if item.is_file()):
                relative = source.relative_to(assets).as_posix()
                hash_name = self._lookup_hash(cursor, relative, source)
                if not hash_name:
                    continue
                name = Path(hash_name).name
                if len(name) < 2:
                    continue
                target = (Path(name[:2]) / name).as_posix()
                if target not in prepared_files:
                    continue
                previous = owners.get(target)
                if previous is not None and previous != relative:
                    raise StoreError(
                        "Two source assets resolve to the same target hash: "
                        f"{previous!r} and {relative!r} -> {target}."
                    )
                owners[target] = relative
                mapping[relative] = target
        finally:
            connection.close()
        return mapping

    @staticmethod
    def _lookup_hash(cursor, relative: str, source: Path) -> str:
        cursor.execute("SELECT h FROM a WHERE n=?", (relative,))
        row = cursor.fetchone()
        if row and row[0]:
            return str(row[0])

        try:
            with source.open("rb") as handle:
                if not handle.read(8).startswith(b"UnityFS"):
                    return ""
            import UnityPy

            environment = UnityPy.load(str(source))
            for obj in environment.objects:
                if obj.type.name != "AssetBundle":
                    continue
                bundle = obj.read()
                resolved_name = os.path.splitext(str(bundle.m_Name or ""))[0]
                if not resolved_name:
                    continue
                cursor.execute("SELECT h FROM a WHERE n=?", (resolved_name,))
                row = cursor.fetchone()
                if row and row[0]:
                    return str(row[0])
        except Exception:
            return ""
        return ""

    def _decoder(self):
        if sys.platform != "win32" and "winreg" not in sys.modules:
            stub = types.ModuleType("winreg")
            stub.HKEY_CURRENT_USER = object()
            stub.HKEY_LOCAL_MACHINE = object()
            sys.modules["winreg"] = stub
        try:
            import UMML_core as core
        except Exception as exc:
            raise StoreError(f"Could not load UMML's asset adapter: {exc}") from exc

        meta_path = str(self.meta_path)

        class Decoder:
            progress_bar = _NullWidget()
            progress_label = _NullWidget()
            root = _NullRoot()

            def __init__(self):
                self.meta_path = meta_path

            @staticmethod
            def scan_full_path(root):
                root_path = Path(root)
                for item in root_path.rglob("*"):
                    if item.is_file():
                        yield item.relative_to(root_path).as_posix()

        Decoder.decrypt_assets_internal = core.ModLoaderGUI.decrypt_assets_internal
        return Decoder()

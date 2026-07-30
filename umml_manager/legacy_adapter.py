from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import struct
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

_AB_KEY = b"\x53\x2B\x46\x31\xE4\xA7\xB9\x47\x3E\x7C\xFB"


class _NullWidget:
    def __setitem__(self, key, value):
        return None

    def config(self, **kwargs):
        return None


class _NullRoot:
    def update_idletasks(self):
        return None


class LegacyAssetAdapter:
    """Prepare legacy UMML assets without allowing profile options to mutate sources."""

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

    def _prepare_locked(
        self,
        record: ModRecord,
        assets: Path,
        output: Path,
    ) -> ModRecord:
        if record.option_groups:
            return self._prepare_configurable_locked(record, assets, output)

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
            updated = replace(
                record,
                prepared_path=str(output),
                files=files,
                source_files=source_files,
                source_hashes={},
                source_roots={},
                prepared_against=hash_file(self.meta_path),
                prepared_at=datetime.now(timezone.utc).isoformat(),
            )
            return self._commit_prepared(
                updated,
                output=output,
                normalized=normalized,
                backup=backup,
                moved_old_ref=[moved_old],
                moved_new_ref=[moved_new],
            )
        finally:
            shutil.rmtree(stage_root, ignore_errors=True)
            if backup.exists() and not output.exists():
                os.replace(backup, output)

    def _prepare_configurable_locked(
        self,
        record: ModRecord,
        assets: Path,
        output: Path,
    ) -> ModRecord:
        """Preserve each authored source payload, even when variants share a target."""

        stage_root = Path(
            tempfile.mkdtemp(prefix=f".{output.name}-prepare-", dir=output.parent)
        )
        normalized = stage_root / "normalized"
        normalized.mkdir()
        backup = output.with_name(
            f".{output.name}.previous-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        )
        moved_old = False
        moved_new = False
        missing = 0
        source_files: dict[str, str] = {}
        source_hashes: dict[str, str] = {}
        source_roots: dict[str, str] = {}
        try:
            try:
                connection = sqlite3.connect(str(self.meta_path))
            except sqlite3.Error as exc:
                raise StoreError(f"Could not open metadata for configurable preparation: {exc}") from exc
            try:
                cursor = connection.cursor()
                cursor.execute("PRAGMA table_info(a)")
                columns = {str(row[1]) for row in cursor.fetchall()}
                if "n" not in columns or "h" not in columns:
                    raise StoreError("Metadata table a is missing source-name/hash columns")
                has_encrypt = "e" in columns

                for source in sorted(item for item in assets.rglob("*") if item.is_file()):
                    relative = source.relative_to(assets).as_posix()
                    row = self._lookup_asset_row(
                        cursor,
                        relative,
                        source,
                        has_encrypt=has_encrypt,
                    )
                    if row is None:
                        if self._looks_like_game_asset(source):
                            missing += 1
                        continue
                    hash_name, encryption_key = row
                    name = Path(hash_name).name
                    if len(name) < 2:
                        missing += 1
                        continue
                    target = (Path(name[:2]) / name).as_posix()
                    root_relative = (
                        Path("sources")
                        / hashlib.sha256(relative.encode("utf-8")).hexdigest()[:20]
                    ).as_posix()
                    destination = normalized / root_relative / target
                    self._decode_source(source, destination, encryption_key)
                    source_files[relative] = target
                    source_hashes[relative] = hash_file(destination)
                    source_roots[relative] = root_relative
            finally:
                connection.close()

            if not source_files:
                raise StoreError(
                    f"No compatible configurable assets produced; {missing} entries were absent "
                    "from metadata. The previous prepared cache was preserved."
                )
            try:
                selected_sources = select_source_paths(
                    record.option_groups,
                    {},
                    source_files,
                )
            except OptionError as exc:
                raise StoreError(f"Invalid configurable mod manifest: {exc}") from exc

            files: dict[str, str] = {}
            owners: dict[str, str] = {}
            for source_relative in sorted(selected_sources):
                target = source_files[source_relative]
                previous = owners.get(target)
                if previous is not None:
                    raise StoreError(
                        "The default configurable selection contains two sources for one game target: "
                        f"{previous!r} and {source_relative!r} -> {target}. Put them in mutually "
                        "exclusive choices or remove the duplicate shared file."
                    )
                owners[target] = source_relative
                files[target] = source_hashes[source_relative]
            if not files:
                raise StoreError(
                    "The default configurable selection produced no deployable assets; "
                    "the previous prepared cache was preserved."
                )

            updated = replace(
                record,
                prepared_path=str(output),
                files=files,
                source_files=source_files,
                source_hashes=source_hashes,
                source_roots=source_roots,
                prepared_against=hash_file(self.meta_path),
                prepared_at=datetime.now(timezone.utc).isoformat(),
            )
            return self._commit_prepared(
                updated,
                output=output,
                normalized=normalized,
                backup=backup,
                moved_old_ref=[moved_old],
                moved_new_ref=[moved_new],
            )
        finally:
            shutil.rmtree(stage_root, ignore_errors=True)
            if backup.exists() and not output.exists():
                os.replace(backup, output)

    def _commit_prepared(
        self,
        updated: ModRecord,
        *,
        output: Path,
        normalized: Path,
        backup: Path,
        moved_old_ref: list[bool],
        moved_new_ref: list[bool],
    ) -> ModRecord:
        if output.exists():
            os.replace(output, backup)
            moved_old_ref[0] = True
        os.replace(normalized, output)
        moved_new_ref[0] = True
        try:
            self.store.save_mod(updated)
        except Exception:
            if moved_new_ref[0] and output.exists():
                shutil.rmtree(output, ignore_errors=True)
            if moved_old_ref[0] and backup.exists():
                os.replace(backup, output)
            raise
        shutil.rmtree(backup, ignore_errors=True)
        return updated

    def _source_target_map(
        self,
        assets: Path,
        prepared_files: dict[str, str],
    ) -> dict[str, str]:
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

    @classmethod
    def _lookup_asset_row(
        cls,
        cursor,
        relative: str,
        source: Path,
        *,
        has_encrypt: bool,
    ) -> tuple[str, int] | None:
        cursor.execute(
            "SELECT h, e FROM a WHERE n=?" if has_encrypt else "SELECT h FROM a WHERE n=?",
            (relative,),
        )
        row = cursor.fetchone()
        if row and row[0]:
            return str(row[0]), int(row[1]) if has_encrypt else 0

        resolved_name = cls._unity_bundle_name(source)
        if not resolved_name:
            return None
        cursor.execute(
            "SELECT h, e FROM a WHERE n=?" if has_encrypt else "SELECT h FROM a WHERE n=?",
            (resolved_name,),
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return None
        return str(row[0]), int(row[1]) if has_encrypt else 0

    @classmethod
    def _lookup_hash(cls, cursor, relative: str, source: Path) -> str:
        cursor.execute("SELECT h FROM a WHERE n=?", (relative,))
        row = cursor.fetchone()
        if row and row[0]:
            return str(row[0])
        resolved_name = cls._unity_bundle_name(source)
        if not resolved_name:
            return ""
        cursor.execute("SELECT h FROM a WHERE n=?", (resolved_name,))
        row = cursor.fetchone()
        return str(row[0]) if row and row[0] else ""

    @staticmethod
    def _unity_bundle_name(source: Path) -> str:
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
                resolved = os.path.splitext(str(bundle.m_Name or ""))[0]
                if resolved:
                    return resolved
        except Exception:
            return ""
        return ""

    @staticmethod
    def _looks_like_game_asset(source: Path) -> bool:
        if source.suffix.casefold() in {".acb", ".awb", ".usm"}:
            return True
        try:
            return source.read_bytes()[:8].startswith(b"UnityFS")
        except OSError:
            return False

    @staticmethod
    def _decode_source(source: Path, destination: Path, encryption_key: int) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if encryption_key == 0:
            atomic_copy_file(source, destination)
            return
        data = bytearray(source.read_bytes())
        if len(data) > 256:
            key = LegacyAssetAdapter._derive_asset_key(encryption_key)
            for index in range(256, len(data)):
                data[index] ^= key[index % len(key)]
        destination.write_bytes(data)

    @staticmethod
    def _derive_asset_key(key_long: int) -> bytes:
        key_bytes = struct.pack("<q", key_long)
        final = bytearray(len(_AB_KEY) * 8)
        for index, value in enumerate(_AB_KEY):
            offset = index * 8
            for byte_index in range(8):
                final[offset + byte_index] = value ^ key_bytes[byte_index]
        return bytes(final)

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
                for path in root_path.rglob("*"):
                    if path.is_file():
                        yield path.relative_to(root_path).as_posix()

        decoder = Decoder()
        decoder.decrypt_assets_internal = types.MethodType(
            core.UMMLApp.decrypt_assets_internal,
            decoder,
        )
        return decoder

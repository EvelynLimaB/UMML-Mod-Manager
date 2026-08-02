from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable

from .extractor_host import ExtractorHostError, validate_supported_requirements

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 4096
MAX_EXPANDED_BYTES = 1024 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MANAGED_METADATA = "managed-extractor.json"
WERSETER_REQUIRED = (
    "main.py",
    "memory.py",
    "game_structs.py",
    "json_encoders.py",
    "requirements.txt",
)


class ExternalToolPackageError(RuntimeError):
    """Raised when a selected external-tool package is unsafe or unsupported."""


@dataclass(frozen=True)
class ExtractorPackageInspection:
    provider: str
    version: str
    archive_sha256: str
    source_root: str
    entrypoint: str
    requirements: str
    python_requirement: str


@dataclass(frozen=True)
class ManagedExtractor:
    provider: str
    version: str
    archive_sha256: str
    installed_at: str
    install_root: str
    source_root: str
    entrypoint: str
    python_executable: str = ""
    runtime_ready: bool = False
    runtime_message: str = ""

    @property
    def path(self) -> Path:
        return Path(self.entrypoint)


@dataclass(frozen=True)
class _ArchiveMember:
    info: zipfile.ZipInfo
    relative: PurePosixPath


def inspect_extractor_archive(archive: str | Path) -> ExtractorPackageInspection:
    source = _validate_archive_path(archive)
    digest = _hash_file(source)
    with zipfile.ZipFile(source) as package:
        members = _safe_members(package)
        root = _detect_source_root(member.relative for member in members)
        files = {
            member.relative.relative_to(root).as_posix()
            for member in members
            if not member.info.is_dir() and _is_within(member.relative, root)
        }
        if not set(WERSETER_REQUIRED).issubset(files):
            raise ExternalToolPackageError(
                "This ZIP is not a recognized Werseter/umadump source package. "
                "Expected main.py, memory.py, game_structs.py, json_encoders.py, "
                "and requirements.txt under one project root."
            )
        version = _detect_werseter_version(package, members, root)
    return ExtractorPackageInspection(
        provider="Werseter/umadump",
        version=version,
        archive_sha256=digest,
        source_root=root.as_posix(),
        entrypoint="main.py",
        requirements="requirements.txt",
        python_requirement="3.14+",
    )


def install_extractor_archive(
    archive: str | Path,
    tools_root: str | Path,
    *,
    create_runtime: bool = True,
    python_command: Iterable[str] | None = None,
) -> ManagedExtractor:
    """Safely install a recognized external extractor from a source ZIP.

    Source bytes are copied into an immutable, hash-addressed directory. When a
    compatible Python 3.14 interpreter is available, source/development builds
    can create a private virtual environment. Standalone Manager packages use
    their bundled host instead. The upstream source is never imported into the
    Manager GUI process.
    """

    source = _validate_archive_path(archive)
    inspection = inspect_extractor_archive(source)
    root = Path(tools_root).expanduser().resolve()
    provider_root = root / "werseter-umadump"
    install_name = (
        f"{_safe_component(inspection.version)}-"
        f"{inspection.archive_sha256[:12]}"
    )
    destination = provider_root / install_name
    metadata_path = destination / MANAGED_METADATA
    if metadata_path.is_file():
        return load_managed_extractor(destination)

    provider_root.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{install_name}.", dir=provider_root)
    )
    try:
        source_root = staging / "source"
        source_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as package:
            members = _safe_members(package)
            archive_root = PurePosixPath(inspection.source_root)
            for member in members:
                if (
                    member.info.is_dir()
                    or not _is_within(member.relative, archive_root)
                ):
                    continue
                relative = member.relative.relative_to(archive_root)
                if not relative.parts:
                    continue
                target = source_root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with (
                    package.open(member.info, "r") as incoming,
                    target.open("xb") as output,
                ):
                    shutil.copyfileobj(
                        incoming,
                        output,
                        length=1024 * 1024,
                    )

        entrypoint = source_root / inspection.entrypoint
        requirements = source_root / inspection.requirements
        if not entrypoint.is_file() or not requirements.is_file():
            raise ExternalToolPackageError(
                "The extractor package changed while it was being installed."
            )
        try:
            validate_supported_requirements(requirements)
        except ExtractorHostError as exc:
            raise ExternalToolPackageError(str(exc)) from exc

        runtime_ready = False
        runtime_message = (
            "Source installed. A compatible bundled host or external Python "
            "3.14 runtime is required to run it."
        )
        if create_runtime:
            command = tuple(python_command or _find_python_314_command())
            if command:
                _verify_python_314(command)
                environment = staging / "runtime"
                _run_checked(
                    (*command, "-m", "venv", str(environment)),
                    "create the extractor's private Python environment",
                    timeout=240,
                )
                runtime_python = _venv_python(environment)
                _run_checked(
                    (
                        str(runtime_python),
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--no-input",
                        "--requirement",
                        str(requirements),
                    ),
                    "install the extractor's declared Python requirements",
                    timeout=600,
                )
                runtime_ready = True
                runtime_message = "Private Python 3.14 environment ready."

        provisional = ManagedExtractor(
            provider=inspection.provider,
            version=inspection.version,
            archive_sha256=inspection.archive_sha256,
            installed_at=datetime.now(timezone.utc).isoformat(),
            install_root=str(destination),
            source_root=str(destination / "source"),
            entrypoint=str(
                destination / "source" / inspection.entrypoint
            ),
            python_executable=(
                str(destination / "runtime" / _venv_relative_python())
                if runtime_ready
                else ""
            ),
            runtime_ready=runtime_ready,
            runtime_message=runtime_message,
        )
        (staging / MANAGED_METADATA).write_text(
            json.dumps(asdict(provisional), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            os.replace(staging, destination)
        except OSError:
            if metadata_path.is_file():
                shutil.rmtree(staging, ignore_errors=True)
                return load_managed_extractor(destination)
            raise
        return load_managed_extractor(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def load_managed_extractor(root: str | Path) -> ManagedExtractor:
    install_root = Path(root).expanduser().resolve()
    metadata_path = install_root / MANAGED_METADATA
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalToolPackageError(
            "Managed extractor metadata is unavailable: "
            f"{metadata_path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ExternalToolPackageError(
            "Managed extractor metadata must be an object"
        )
    result = ManagedExtractor(
        provider=str(value.get("provider") or ""),
        version=str(value.get("version") or ""),
        archive_sha256=str(value.get("archive_sha256") or ""),
        installed_at=str(value.get("installed_at") or ""),
        install_root=str(value.get("install_root") or install_root),
        source_root=str(value.get("source_root") or install_root / "source"),
        entrypoint=str(
            value.get("entrypoint")
            or install_root / "source" / "main.py"
        ),
        python_executable=str(value.get("python_executable") or ""),
        runtime_ready=bool(value.get("runtime_ready")),
        runtime_message=str(value.get("runtime_message") or ""),
    )
    if result.provider != "Werseter/umadump":
        raise ExternalToolPackageError(
            "Unsupported managed extractor provider"
        )
    if not Path(result.entrypoint).is_file():
        raise ExternalToolPackageError(
            f"Managed extractor entry point is missing: {result.entrypoint}"
        )
    if (
        result.runtime_ready
        and not Path(result.python_executable).is_file()
    ):
        raise ExternalToolPackageError(
            "Managed extractor Python runtime is missing: "
            f"{result.python_executable}"
        )
    return result


def _validate_archive_path(archive: str | Path) -> Path:
    source = Path(archive).expanduser().resolve()
    try:
        mode = source.lstat().st_mode
        size = source.stat().st_size
    except OSError as exc:
        raise ExternalToolPackageError(
            f"Extractor ZIP is unavailable: {source}: {exc}"
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ExternalToolPackageError(
            "Extractor package must be a regular ZIP file"
        )
    if source.suffix.casefold() != ".zip":
        raise ExternalToolPackageError(
            "Extractor source package must be a .zip file"
        )
    if size > MAX_ARCHIVE_BYTES:
        raise ExternalToolPackageError(
            "Extractor ZIP exceeds the "
            f"{MAX_ARCHIVE_BYTES // (1024 * 1024)} MiB safety limit"
        )
    if not zipfile.is_zipfile(source):
        raise ExternalToolPackageError(
            "Selected extractor package is not a valid ZIP archive"
        )
    return source


def _safe_members(package: zipfile.ZipFile) -> list[_ArchiveMember]:
    infos = package.infolist()
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise ExternalToolPackageError(
            f"Extractor ZIP has {len(infos):,} entries; the safety limit is "
            f"{MAX_ARCHIVE_ENTRIES:,}"
        )
    total = 0
    result: list[_ArchiveMember] = []
    seen: set[str] = set()
    for info in infos:
        if info.flag_bits & 0x1:
            raise ExternalToolPackageError(
                "Encrypted ZIP entries are not supported"
            )
        relative = PurePosixPath(info.filename.replace("\\", "/"))
        if (
            not relative.parts
            or relative.is_absolute()
            or any(part in {"", ".", ".."} for part in relative.parts)
            or any(part.endswith(":") for part in relative.parts)
        ):
            raise ExternalToolPackageError(
                f"Unsafe extractor ZIP path: {info.filename}"
            )
        mode = (info.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ExternalToolPackageError(
                "Links and special files are not allowed in extractor ZIPs: "
                f"{info.filename}"
            )
        if info.file_size > MAX_MEMBER_BYTES:
            raise ExternalToolPackageError(
                "Extractor ZIP entry exceeds the "
                f"{MAX_MEMBER_BYTES // (1024 * 1024)} MiB limit: "
                f"{info.filename}"
            )
        total += info.file_size
        if total > MAX_EXPANDED_BYTES:
            raise ExternalToolPackageError(
                "Extractor ZIP expands beyond the "
                f"{MAX_EXPANDED_BYTES // (1024 * 1024)} MiB limit"
            )
        key = relative.as_posix().casefold()
        if key in seen:
            raise ExternalToolPackageError(
                f"Duplicate extractor ZIP path: {info.filename}"
            )
        seen.add(key)
        result.append(_ArchiveMember(info, relative))
    return result


def _detect_source_root(
    paths: Iterable[PurePosixPath],
) -> PurePosixPath:
    values = list(paths)
    candidates: set[PurePosixPath] = set()
    required = set(WERSETER_REQUIRED)
    path_strings = {value.as_posix() for value in values}
    for value in values:
        for parent in (value.parent, *value.parents):
            if parent == PurePosixPath("."):
                parent = PurePosixPath()
            if all(
                (
                    (parent / name).as_posix()
                    if parent.parts
                    else name
                )
                in path_strings
                for name in required
            ):
                candidates.add(parent)
    if len(candidates) != 1:
        raise ExternalToolPackageError(
            "Extractor ZIP must contain exactly one recognizable project root"
        )
    return next(iter(candidates))


def _detect_werseter_version(
    package: zipfile.ZipFile,
    members: list[_ArchiveMember],
    root: PurePosixPath,
) -> str:
    update_path = root / "update_check.py"
    for member in members:
        if member.relative == update_path and not member.info.is_dir():
            text = package.read(member.info).decode(
                "utf-8",
                errors="replace",
            )
            match = re.search(
                r"^\s*CURRENT_VERSION\s*=\s*['\"]([^'\"]+)['\"]",
                text,
                flags=re.MULTILINE,
            )
            if match:
                return match.group(1).strip()
    for part in reversed(root.parts):
        match = re.search(
            r"(\d+(?:\.\d+)+(?:[-+._a-zA-Z0-9]*)?)",
            part,
        )
        if match:
            return match.group(1)
    return "unknown"


def _find_python_314_command() -> tuple[str, ...]:
    import sys

    if (
        sys.version_info >= (3, 14)
        and not getattr(sys, "frozen", False)
    ):
        return (sys.executable,)
    if os.name == "nt":
        launcher = shutil.which("py") or shutil.which("py.exe")
        if launcher:
            command = (launcher, "-3.14")
            if _python_command_is_314(command):
                return command
        candidates = ("python3.14.exe", "python.exe", "python3.exe")
    else:
        candidates = ("python3.14", "python3", "python")
    for name in candidates:
        executable = shutil.which(name)
        if executable and _python_command_is_314((executable,)):
            return (executable,)
    return ()


def _python_command_is_314(command: tuple[str, ...]) -> bool:
    try:
        result = subprocess.run(
            (
                *command,
                "-c",
                "import sys;print(int(sys.version_info >= (3,14)))",
            ),
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip() == "1"


def _verify_python_314(command: tuple[str, ...]) -> None:
    if not _python_command_is_314(command):
        raise ExternalToolPackageError(
            "Werseter/umadump requires Python 3.14 or newer. "
            "The selected interpreter is older or unavailable."
        )


def _run_checked(
    command: tuple[str, ...],
    purpose: str,
    *,
    timeout: int,
) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExternalToolPackageError(
            f"Timed out while trying to {purpose}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        output = "\n".join(
            part.strip()
            for part in (exc.stdout, exc.stderr)
            if part and part.strip()
        )
        if len(output) > 1200:
            output = output[-1200:]
        raise ExternalToolPackageError(
            f"Could not {purpose}."
            + (f"\n\n{output}" if output else "")
        ) from exc
    except OSError as exc:
        raise ExternalToolPackageError(
            f"Could not {purpose}: {exc}"
        ) from exc


def _venv_relative_python() -> Path:
    if os.name == "nt":
        return Path("Scripts/python.exe")
    return Path("bin/python")


def _venv_python(environment: Path) -> Path:
    return environment / _venv_relative_python()


def _is_within(path: PurePosixPath, root: PurePosixPath) -> bool:
    if not root.parts:
        return True
    return path == root or root in path.parents


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned or "unknown"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

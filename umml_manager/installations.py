from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .regions import legacy_region, normalize_region
from .safety import hash_file


class InstallationError(RuntimeError):
    """Raised when UMML cannot find or prepare a compatible installation."""


@dataclass(frozen=True)
class InstallationCandidate:
    key: str
    label: str
    region: str
    game_dir: Path
    dat_path: Path
    meta_source: Path


@dataclass(frozen=True)
class ManagerInstallation:
    key: str
    label: str
    region: str
    game_dir: Path
    dat_path: Path
    meta_source: Path
    meta_path: Path
    metadata_fingerprint: str = ""


Decryptor = Callable[[Path, Path, str], Path]


def detect_installation_candidates() -> list[InstallationCandidate]:
    """Return complete, currently accessible installations without decrypting metadata."""

    from .platform_bridge import detect_installations

    candidates: list[InstallationCandidate] = []
    rejected: list[str] = []
    for item in detect_installations():
        if not getattr(item, "detected", False):
            continue
        if item.game_dir is None or item.dat_path is None or item.meta_path is None:
            rejected.append(f"{item.label}: detector omitted a required path")
            continue
        try:
            game_dir = Path(item.game_dir).expanduser().resolve()
            dat_path = Path(item.dat_path).expanduser().resolve()
            meta_source = Path(item.meta_path).expanduser().resolve()
        except OSError as exc:
            rejected.append(f"{item.label}: path resolution failed ({exc})")
            continue
        problems = []
        if not game_dir.is_dir():
            problems.append(f"game directory missing: {game_dir}")
        if not dat_path.is_dir():
            problems.append(f"asset directory missing: {dat_path}")
        if not meta_source.is_file():
            problems.append(f"metadata source missing: {meta_source}")
        if problems:
            rejected.append(f"{item.label}: " + "; ".join(problems))
            continue
        candidates.append(
            InstallationCandidate(
                key=str(item.key),
                label=str(item.label),
                region=normalize_region(str(item.region)),
                game_dir=game_dir,
                dat_path=dat_path,
                meta_source=meta_source,
            )
        )
    if not candidates:
        details = "\n".join(f"- {reason}" for reason in rejected)
        suffix = f"\nDetected but unusable entries:\n{details}" if details else ""
        raise InstallationError(
            "No complete Umamusume installation was detected. Launch the game once, "
            "let its data finish downloading, then run diagnostics."
            + suffix
        )
    candidates.sort(key=lambda item: (item.region, item.label.casefold(), item.key))
    return candidates


def detect_preferred_installation(
    preferred_region: str = "",
    *,
    decryptor: Decryptor | None = None,
) -> ManagerInstallation:
    """Detect the preferred installation and prepare its readable metadata cache."""

    candidates = detect_installation_candidates()
    preferred = normalize_region(preferred_region)
    selected = next(
        (item for item in candidates if item.region == preferred),
        candidates[0],
    )
    return prepare_installation(selected, decryptor=decryptor)


def prepare_installation(
    candidate: InstallationCandidate,
    *,
    decryptor: Decryptor | None = None,
) -> ManagerInstallation:
    """Prepare one already validated candidate for manager use."""

    prepare = decryptor or prepare_metadata_database
    try:
        meta_path = Path(
            prepare(
                candidate.dat_path,
                candidate.meta_source,
                legacy_region(candidate.region),
            )
        ).expanduser().resolve()
    except InstallationError:
        raise
    except Exception as exc:
        raise InstallationError(
            f"Could not prepare metadata for {candidate.label}: {exc}"
        ) from exc
    if not meta_path.is_file():
        raise InstallationError(
            f"Prepared metadata database does not exist: {meta_path}"
        )
    try:
        fingerprint = hash_file(meta_path)
    except OSError as exc:
        raise InstallationError(
            f"Could not fingerprint prepared metadata database: {meta_path}: {exc}"
        ) from exc
    return ManagerInstallation(
        key=candidate.key,
        label=candidate.label,
        region=candidate.region,
        game_dir=candidate.game_dir,
        dat_path=candidate.dat_path,
        meta_source=candidate.meta_source,
        meta_path=meta_path,
        metadata_fingerprint=fingerprint,
    )


def prepare_metadata_database(
    dat_path: Path,
    meta_path: Path,
    region: str,
) -> Path:
    """Return a readable metadata DB, creating the cached decrypted copy if needed."""

    if not dat_path.is_dir():
        raise InstallationError(f"Asset directory does not exist: {dat_path}")
    if not meta_path.is_file():
        raise InstallationError(f"Encrypted metadata source does not exist: {meta_path}")
    if sys.platform != "win32" and "winreg" not in sys.modules:
        stub = types.ModuleType("winreg")
        stub.HKEY_CURRENT_USER = object()
        stub.HKEY_LOCAL_MACHINE = object()
        sys.modules["winreg"] = stub

    try:
        import UMML_core as core
    except Exception as exc:
        raise InstallationError(
            f"Could not load UMML metadata support: {exc}"
        ) from exc

    try:
        prepared = core.load_or_decrypt_meta_simple(
            str(dat_path),
            str(meta_path),
            legacy_region(region),
        )
    except Exception as exc:
        raise InstallationError(
            f"Could not prepare the metadata database: {exc}"
        ) from exc
    return Path(prepared)

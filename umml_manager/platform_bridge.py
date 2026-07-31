"""Fresh platform discovery for Manager entry points.

The legacy application activates :mod:`umml_autodetect` by monkey-patching
``umml_platform`` during startup.  Manager entry points do not import that
legacy bootstrap, so they need an explicit bridge to the same robust Linux
detector.  Keeping the bridge local to Manager avoids process-global patches
and guarantees that every retry performs a fresh Steam/Proton scan.
"""

from __future__ import annotations

import os
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import umml_platform
from umml_autodetect import (
    DiscoveryResult,
    discover_global_installation,
    format_discovery_report,
)

IS_WINDOWS = os.name == "nt"


def _legacy_installations() -> list[umml_platform.GameInstallation]:
    """Run compatibility discovery without corrupting CLI JSON with prints."""

    with redirect_stdout(StringIO()):
        return list(umml_platform.detect_installations())


def _with_robust_global(
    installations: list[umml_platform.GameInstallation],
    current: DiscoveryResult,
) -> list[umml_platform.GameInstallation]:
    """Return a copy with Steam Global replaced by one robust scan."""

    merged = list(installations)
    note_parts = ["Steam app 3224770"]
    if current.game_candidates:
        note_parts.append(current.game_candidates[0].source)
    if current.data_candidates:
        note_parts.append(current.data_candidates[0].source)
    replacement = umml_platform.GameInstallation(
        key="steam-global",
        label="Steam Global",
        region="Global",
        game_dir=current.game_dir,
        data_dir=current.data_dir,
        meta_path=current.data_dir / "meta" if current.data_dir else None,
        note="; ".join(note_parts),
    )

    for index, item in enumerate(merged):
        if item.key == "steam-global":
            merged[index] = replacement
            break
    else:
        merged.insert(0, replacement)
    return merged


def detect_installations() -> list[umml_platform.GameInstallation]:
    """Return platform installations with robust Linux Steam Global results."""

    installations = _legacy_installations()
    if IS_WINDOWS:
        return installations
    return _with_robust_global(
        installations,
        discover_global_installation(),
    )


def format_doctor_report() -> tuple[str, bool]:
    """Return one consistent Manager platform report and readiness verdict."""

    if IS_WINDOWS:
        return umml_platform.format_doctor_report()

    current = discover_global_installation()
    installations = _with_robust_global(
        _legacy_installations(),
        current,
    )
    lines = [
        "UMML Manager platform doctor",
        f"Python: {sys.version.split()[0]}",
        f"Platform: {sys.platform} ({os.name})",
        f"Home: {Path.home()}",
        "",
        format_discovery_report(current),
        "",
        "Supported installations:",
    ]
    ready = False
    for item in installations:
        if not item.supported:
            lines.append(f"  [SKIP] {item.label}: {item.status_text}")
            continue
        writable = bool(
            item.detected
            and item.dat_path
            and os.access(item.dat_path, os.W_OK)
        )
        marker = "OK" if writable else "CHECK"
        lines.append(f"  [{marker}] {item.label}: {item.status_text}")
        if item.game_dir:
            lines.append(f"      game: {item.game_dir}")
        if item.meta_path:
            lines.append(f"      meta: {item.meta_path}")
        if item.dat_path:
            lines.append(f"      dat: {item.dat_path}")
        if item.detected:
            lines.append(f"      writable: {'yes' if writable else 'NO'}")
        ready = ready or writable

    lines.append(f"\nMANAGER RESULT: {'READY' if ready else 'NOT READY'}")
    if not ready:
        lines.append(
            "Launch the game once and let its data download finish. "
            "The Steam autodetect evidence above identifies the missing half."
        )
    return "\n".join(lines), ready

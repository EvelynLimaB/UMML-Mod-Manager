from __future__ import annotations

import sys
from pathlib import Path


def manager_version() -> str:
    candidates = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "MANAGER_VERSION")
    candidates.append(Path(__file__).resolve().parents[1] / "MANAGER_VERSION")
    for path in candidates:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return "0+unknown"

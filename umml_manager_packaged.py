#!/usr/bin/env python3
"""Single frozen entry point for the Manager GUI, CLI, and private hosts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def manager_version() -> str:
    try:
        return _resource_path("MANAGER_VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0+unknown"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"--version", "-V"}:
        print(manager_version())
        return 0
    if args and args[0] == "--extractor-host-probe":
        from umml_manager.extractor_host import runtime_probe

        print(json.dumps(runtime_probe(), sort_keys=True))
        return 0
    if args and args[0] == "--extractor-host":
        args.pop(0)
        from umml_manager.extractor_host import main as extractor_host_main

        return extractor_host_main(args)
    if args and args[0] == "--legacy-host":
        args.pop(0)
        from umml_manager.legacy_host import main as legacy_main

        return legacy_main(args)

    mode = args.pop(0) if args and args[0] in {"gui", "cli"} else "gui"
    if mode == "cli":
        from umml_manager.cli import main as cli_main

        return cli_main(args)
    from umml_manager.gui import main as gui_main

    return gui_main(args)


if __name__ == "__main__":
    raise SystemExit(main())

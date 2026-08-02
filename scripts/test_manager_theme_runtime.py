#!/usr/bin/env python3
"""Render one Manager GUI runtime with both supported visual palettes."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

THEMES = ("light", "dark")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Manager GUI smoke-test command once with the Light palette "
            "and once with the Dark palette."
        )
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help=(
            "GUI command prefix, for example: "
            "-- python3 -m umml_manager.gui"
        ),
    )
    return parser


def _run_source_script(env: dict[str, str], theme: str, script_name: str, label: str) -> int:
    script = Path(__file__).with_name(script_name)
    completed = subprocess.run(
        [sys.executable, str(script)],
        env=env,
        check=False,
    )
    if completed.returncode:
        print(
            f"Manager {theme} {label} failed with exit {completed.returncode}",
            file=sys.stderr,
        )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("a Manager GUI command is required after --")

    for theme in THEMES:
        env = os.environ.copy()
        env["UMML_SYSTEM_THEME"] = theme
        for script_name, label in (
            ("test_manager_responsive_runtime.py", "responsive source smoke test"),
            ("test_manager_veteran_roster_runtime.py", "veteran roster source smoke test"),
        ):
            status = _run_source_script(env, theme, script_name, label)
            if status:
                return status
        completed = subprocess.run(
            [*command, "--smoke-test"],
            env=env,
            check=False,
        )
        if completed.returncode:
            print(
                f"Manager {theme} theme smoke test failed with exit "
                f"{completed.returncode}: {' '.join(command)}",
                file=sys.stderr,
            )
            return completed.returncode
        print(f"Manager {theme} theme smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

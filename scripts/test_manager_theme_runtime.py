#!/usr/bin/env python3
"""Render one Manager GUI runtime with both supported visual palettes."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

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

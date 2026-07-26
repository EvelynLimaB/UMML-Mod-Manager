#!/usr/bin/env python3
"""Verify one Manager runtime against a native Debian/Mint Steam layout."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

APP_ID = 3224770


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run a Manager CLI command against a disposable "
            "~/.steam/debian-installation fixture."
        )
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help=(
            "Manager CLI prefix, for example: "
            "-- python3 -m umml_manager"
        ),
    )
    return parser


def create_mint_fixture(root: Path) -> tuple[Path, Path, Path]:
    home = root / "home"
    steamapps = (
        home
        / ".steam"
        / "debian-installation"
        / "steamapps"
    )
    game = steamapps / "common" / "UmamusumePrettyDerby"
    persistent = (
        game
        / "UmamusumePrettyDerby_Data"
        / "Persistent"
    )
    (persistent / "dat").mkdir(parents=True)
    (persistent / "meta").write_bytes(b"disposable encrypted metadata")
    (game / "UmamusumePrettyDerby.exe").write_bytes(b"MZ")
    (steamapps / f"appmanifest_{APP_ID}.acf").write_text(
        '"AppState"\n'
        "{\n"
        f'    "appid" "{APP_ID}"\n'
        '    "StateFlags" "4"\n'
        '    "installdir" "UmamusumePrettyDerby"\n'
        "}\n",
        encoding="utf-8",
    )
    return home, game, persistent


def platform_check(report: dict[str, object]) -> dict[str, object]:
    checks = report.get("checks")
    if not isinstance(checks, list):
        raise RuntimeError("doctor JSON has no checks list")
    for check in checks:
        if (
            isinstance(check, dict)
            and check.get("name") == "platform-detection"
        ):
            return check
    raise RuntimeError("doctor JSON has no platform-detection check")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command.pop(0)
    if not command:
        raise SystemExit("a Manager CLI command is required after --")

    with tempfile.TemporaryDirectory(
        prefix="umml-manager-mint-autodetect-"
    ) as temporary:
        root = Path(temporary)
        home, game, persistent = create_mint_fixture(root)
        environment = os.environ.copy()
        for name in (
            "UMML_GAME_DIR",
            "UMML_GAME_DIR_3224770",
            "UMML_PERSISTENT_DIR",
            "UMML_STEAM_ROOT",
            "STEAM_DIR",
            "STEAM_ROOT",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH",
            "STEAM_COMPAT_DATA_PATH",
        ):
            environment.pop(name, None)
        environment.update(
            {
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
            }
        )
        completed = subprocess.run(
            [
                *command,
                "--root",
                str(root / "manager-state"),
                "doctor",
                "--json",
            ],
            check=False,
            capture_output=True,
            encoding="utf-8",
            env=environment,
        )
        if completed.returncode not in (0, 2):
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
            raise RuntimeError(
                "Manager doctor exited unexpectedly with "
                f"{completed.returncode}"
            )
        try:
            report = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            print(completed.stdout, end="")
            print(completed.stderr, end="", file=sys.stderr)
            raise RuntimeError("Manager doctor did not return JSON") from exc

        check = platform_check(report)
        detail = str(check.get("detail", ""))
        expected = (
            "Steam autodetect report for app 3224770",
            "native-debian",
            f"game: {game}",
            f"data: {persistent}",
            "result: READY",
            "MANAGER RESULT: READY",
        )
        missing = [text for text in expected if text not in detail]
        if not check.get("passed") or missing:
            print(detail)
            if missing:
                print(
                    "Missing expected evidence: " + ", ".join(missing),
                    file=sys.stderr,
                )
            return 1

        print("Manager Mint/DEB-style autodetection runtime test passed.")
        print(f"Game: {game}")
        print(f"Data: {persistent}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

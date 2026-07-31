#!/usr/bin/env python3
"""Validate public branding without breaking stable compatibility identifiers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Build the obsolete slug from pieces so the audit does not discover its own
# needle and report itself as the final surviving offender. Computers remain
# very literal colleagues.
_OLD_REPOSITORY = "EvelynLimaB/" + "UMML-Linux"
STALE_REPOSITORY_TOKENS = (
    _OLD_REPOSITORY,
    "github.com/" + _OLD_REPOSITORY,
)

PUBLIC_NAME_FILES = {
    "README.md": "# Uma Mod Manager",
    "MANAGER_README.md": "# Uma Mod Manager user guide",
    "CONTRIBUTING.md": "# Contributing to Uma Mod Manager",
    "SECURITY.md": "Uma Mod Manager imports untrusted mod packages",
    "MANAGER_CHANGELOG.md": "# Uma Mod Manager changelog",
    "docs/PROJECT_VISION.md": "# Uma Mod Manager project vision",
    "docs/README.md": "# Uma Mod Manager documentation",
    "packaging/linux/io.github.evelynlimab.ummlmanager.desktop": "Name=Uma Mod Manager",
    "packaging/appimage/io.github.evelynlimab.ummlmanager.desktop": "Name=Uma Mod Manager",
    "packaging/linux/io.github.evelynlimab.ummlmanager.metainfo.xml": "<name>Uma Mod Manager</name>",
    ".github/workflows/manager-checks.yml": "name: Uma Mod Manager Linux checks",
    ".github/workflows/manager-windows-checks.yml": "name: Uma Mod Manager Windows checks",
    ".github/workflows/manager-testing-release.yml": "name: Uma Mod Manager testing release",
    "umml_manager/gui.py": 'PRODUCT_NAME = "Uma Mod Manager"',
    "umml_manager/ui_veterans_window.py": 'window.title("Uma Mod Manager · Veteran Roster")',
}

REQUIRED_FILES = (
    "NOTICE.md",
    "CITATION.cff",
    "docs/BRANDING_AND_COMPATIBILITY.md",
    "docs/TESTING_AND_FEEDBACK.md",
    "docs/RELEASE_PROCESS.md",
)

# These names intentionally remain stable until an explicit state/package
# migration exists. A public rebrand must not create a second empty product.
COMPATIBILITY_CONTRACT = {
    "scripts/build_manager_deb.sh": (
        'PACKAGE="umml-manager"',
        "https://github.com/EvelynLimaB/Uma-Mod-Manager",
    ),
    "packaging/linux/io.github.evelynlimab.ummlmanager.metainfo.xml": (
        "<id>io.github.evelynlimab.ummlmanager</id>",
        "<binary>umml-manager</binary>",
        "<binary>umml-manager-cli</binary>",
    ),
    ".github/workflows/manager-windows-checks.yml": (
        "Uma Mod Manager.cmd",
        "Uma Mod Manager CLI.cmd",
        "UMML Manager.cmd",
        "UMML Manager CLI.cmd",
        'dist/umml-manager_${version}_win64.zip',
    ),
    "docs/BRANDING_AND_COMPATIBILITY.md": (
        "`umml-manager`",
        "`umml_manager`",
        "`io.github.evelynlimab.ummlmanager`",
        "%LOCALAPPDATA%\\UMML Manager",
        "~/.local/share/umml-manager",
    ),
}

UPSTREAM_CONTRACT = {
    "README.md": "https://github.com/tumugu/UmaMusume_Mod_Loader",
    "NOTICE.md": "https://github.com/tumugu/UmaMusume_Mod_Loader",
    "CITATION.cff": "https://github.com/tumugu/UmaMusume_Mod_Loader",
}

SKIP_SUFFIXES = {
    ".7z",
    ".appimage",
    ".bin",
    ".bmp",
    ".bz2",
    ".db",
    ".deb",
    ".dll",
    ".dmp",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lock",
    ".msgpack",
    ".pdf",
    ".png",
    ".pyc",
    ".rar",
    ".so",
    ".sqlite",
    ".tar",
    ".tgz",
    ".webp",
    ".xz",
    ".zip",
}


def _read(relative: str) -> str:
    path = ROOT / relative
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssertionError(
            f"Could not read required branding file {relative}: {exc}"
        ) from exc


def _manager_version() -> str:
    version = _read("MANAGER_VERSION").strip()
    if not version:
        raise AssertionError("MANAGER_VERSION is empty")
    return version


def _tracked_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return [
            path
            for path in ROOT.rglob("*")
            if path.is_file() and ".git" not in path.parts
        ]
    return [
        ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    ]


def _assert_no_stale_repository_urls(errors: list[str]) -> None:
    for path in _tracked_files():
        if path.suffix.casefold() in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(ROOT).as_posix()
        for token in STALE_REPOSITORY_TOKENS:
            if token in text:
                errors.append(
                    f"{relative}: stale repository reference {token!r}"
                )


def main() -> int:
    errors: list[str] = []

    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(
                f"Missing required identity/attribution file: {relative}"
            )

    for relative, expected in PUBLIC_NAME_FILES.items():
        try:
            text = _read(relative)
        except AssertionError as exc:
            errors.append(str(exc))
            continue
        if expected not in text:
            errors.append(
                f"{relative}: missing public identity marker {expected!r}"
            )

    for relative, markers in COMPATIBILITY_CONTRACT.items():
        try:
            text = _read(relative)
        except AssertionError as exc:
            errors.append(str(exc))
            continue
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"{relative}: compatibility marker disappeared: {marker!r}"
                )

    for relative, upstream_url in UPSTREAM_CONTRACT.items():
        try:
            text = _read(relative)
        except AssertionError as exc:
            errors.append(str(exc))
            continue
        if upstream_url not in text:
            errors.append(f"{relative}: original UMML lineage URL is missing")

    try:
        manager_version = _manager_version()
    except AssertionError as exc:
        errors.append(str(exc))
        manager_version = ""

    readme = _read("README.md")
    if "1.5.0-linux.6" not in readme:
        errors.append(
            "README.md: expected preserved compatibility version "
            "'1.5.0-linux.6'"
        )

    if manager_version:
        display = manager_version.replace("~alpha", "-alpha.")
        candidate_surfaces = {
            "MANAGER_VERSION": manager_version,
            "packaging/linux/io.github.evelynlimab.ummlmanager.metainfo.xml": (
                f'version="{display}"'
            ),
            f"docs/releases/{display}.md": display,
        }
        for relative, marker in candidate_surfaces.items():
            try:
                text = _read(relative)
            except AssertionError as exc:
                errors.append(str(exc))
                continue
            if marker not in text:
                errors.append(
                    f"{relative}: current candidate marker disappeared: "
                    f"{marker!r}"
                )

    _assert_no_stale_repository_urls(errors)

    if errors:
        print("Branding audit failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Branding audit passed: public identity, upstream lineage, current "
        "candidate metadata, and stable compatibility names agree."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

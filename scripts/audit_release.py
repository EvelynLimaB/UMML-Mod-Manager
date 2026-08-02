#!/usr/bin/env python3
"""Fail closed when Uma Mod Manager prerelease metadata drifts apart."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)~alpha(?P<number>\d+)$")


class ReleaseAuditError(RuntimeError):
    pass


def manager_version() -> str:
    value = (ROOT / "MANAGER_VERSION").read_text(encoding="utf-8").strip()
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ReleaseAuditError(
            "MANAGER_VERSION must use the Debian-safe testing form "
            "X.Y.Z~alphaN; got " + repr(value)
        )
    return value


def portable_version(version: str) -> str:
    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ReleaseAuditError(f"Unsupported Manager version: {version}")
    return f"{match.group('base')}-alpha.{match.group('number')}"


def release_tag(version: str) -> str:
    return "v" + portable_version(version)


def require_file(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise ReleaseAuditError(f"Required release file is missing: {path}")
    return target.read_text(encoding="utf-8")


def require_contains(path: str, *values: str) -> str:
    text = require_file(path)
    for value in values:
        if value not in text:
            raise ReleaseAuditError(
                f"{path} does not contain required text: {value}"
            )
    return text


def run_audit(expected_tag: str = "") -> dict[str, str]:
    version = manager_version()
    display = portable_version(version)
    tag = release_tag(version)
    if expected_tag and expected_tag != tag:
        raise ReleaseAuditError(
            f"Requested release tag {expected_tag!r} does not match "
            f"MANAGER_VERSION ({tag!r})"
        )

    release_notes = f"docs/releases/{display}.md"

    # README, player-guide, changelog, and citation metadata describe the latest
    # published release until the candidate is actually published. Advertising
    # an unavailable candidate is less useful than keeping one stable public
    # download path. Exact candidate identity instead lives in the version file,
    # release notes, AppStream, package payloads, checksums, and release workflow.
    require_contains(
        "README.md",
        "Community Test",
        "docs/TESTING_AND_FEEDBACK.md",
        "Create support bundle",
    )
    require_contains(
        "MANAGER_README.md",
        "Testing and feedback",
        "Create support bundle",
    )
    require_contains(
        "packaging/linux/io.github.evelynlimab.ummlmanager.metainfo.xml",
        f'version="{display}"',
    )
    require_contains(
        release_notes,
        display,
        "What to test",
        "Known limitations",
        "How to report feedback",
    )
    require_contains(
        "docs/TESTING_AND_FEEDBACK.md",
        "support bundle",
        "Do not attach copyrighted game files",
        "Exact build",
    )
    require_contains(
        "docs/RELEASE_PROCESS.md",
        "prerelease",
        "rollback",
    )
    require_contains(
        ".github/ISSUE_TEMPLATE/testing_feedback.yml",
        "Testing feedback",
        "support bundle",
        "MANAGER_VERSION",
    )
    require_contains(
        "umml_manager/ui_settings.py",
        "Create support bundle",
        "Testing guide",
        "Report feedback",
        "testing_feedback.yml",
    )
    require_contains(
        ".github/workflows/manager-testing-release.yml",
        "workflow_dispatch",
        "scripts/audit_release.py",
        "gh release create",
        f"default: {tag}",
        release_notes,
        "python-version: '3.14'",
        "--extractor-host-probe",
    )
    require_contains(
        "umml_manager/support_bundle.py",
        "game_assets_included",
        "known_paths_and_private_keys_redacted",
    )
    require_contains(
        "tests/test_manager_support_bundle.py",
        "test_bundle_is_small_inspectable_and_redacts_private_data",
    )
    require_contains(
        "requirements.txt",
        "minidump==0.0.24",
    )
    require_contains(
        "umml_manager/extractor_host.py",
        "MINIMUM_PYTHON = (3, 14)",
        "minidump==0.0.24",
        "verified_runtime_probe",
        "validate_supported_requirements",
    )
    require_contains(
        "NOTICE.md",
        "skelsec/minidump",
        "Python 3.14",
    )
    require_contains(
        "third_party/licenses/Python-3.14.6.txt",
        "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2",
        "Copyright (c) 2001 Python Software Foundation",
    )
    require_contains(
        "third_party/licenses/minidump-0.0.24.txt",
        "Copyright (c) 2018 Tamas Jos",
        "MIT License",
    )

    for builder in (
        "scripts/build_manager_deb.sh",
        "scripts/build_manager_appimage.sh",
    ):
        require_contains(
            builder,
            "TESTING_AND_FEEDBACK.md",
            "RELEASE_PROCESS.md",
            "docs/releases/$DISPLAY_VERSION.md",
            "Python-3.14.6-LICENSE.txt",
            "minidump-0.0.24-LICENSE.txt",
        )
    require_contains(
        "packaging/pyinstaller/umml-manager.spec",
        "TESTING_AND_FEEDBACK.md",
        "RELEASE_PROCESS.md",
        f"{display}.md",
        "Python-3.14.6.txt",
        "minidump-0.0.24.txt",
        '"ctypes.wintypes"',
        '"urllib.request"',
    )
    require_contains(
        "scripts/build_manager_frozen.sh",
        "Python 3.14+",
        "--extractor-host-probe",
        'p["host_self_test"]',
    )

    return {
        "manager_version": version,
        "portable_version": display,
        "tag": tag,
        "release_notes": release_notes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tag",
        default="",
        help="require this exact vX.Y.Z-alpha.N tag",
    )
    args = parser.parse_args(argv)
    try:
        report = run_audit(args.tag)
    except (OSError, ReleaseAuditError) as exc:
        print(f"release audit failed: {exc}", file=sys.stderr)
        return 1
    for key, value in report.items():
        print(f"[PASS] {key}: {value}")
    print("RESULT: PASS — testing release metadata is internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import runpy
import stat
import sys
from pathlib import Path

MINIMUM_PYTHON = (3, 14)
SUPPORTED_REQUIREMENTS = {
    "minidump==0.0.24",
    "minidump~=0.0.24",
}
WERSETER_REQUIRED = (
    "main.py",
    "memory.py",
    "game_structs.py",
    "json_encoders.py",
    "requirements.txt",
)


class ExtractorHostError(RuntimeError):
    """Raised when the private extractor host cannot run safely."""


def runtime_probe() -> dict[str, object]:
    """Describe the runtime capabilities shipped with the Manager."""

    try:
        minidump_version = importlib.metadata.version("minidump")
    except importlib.metadata.PackageNotFoundError:
        minidump_version = ""
    return {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "python_314_or_newer": sys.version_info >= MINIMUM_PYTHON,
        "frozen": bool(getattr(sys, "frozen", False)),
        "minidump": minidump_version,
        "ready": bool(
            sys.version_info >= MINIMUM_PYTHON
            and minidump_version == "0.0.24"
        ),
    }


def packaged_host_available() -> bool:
    """Return whether this process can host supported Werseter source."""

    return bool(runtime_probe()["ready"])


def packaged_host_command(
    project: str | Path,
    script: str | Path,
    inbox: str | Path,
) -> tuple[str, ...]:
    """Build a command that starts the host in a separate process."""

    if not packaged_host_available():
        raise ExtractorHostError(
            "The bundled extractor runtime is unavailable. This build must "
            "contain Python 3.14+ and minidump 0.0.24."
        )
    if getattr(sys, "frozen", False):
        return (
            sys.executable,
            "--extractor-host",
            str(Path(project).expanduser().resolve()),
            str(Path(script).expanduser().resolve()),
            str(Path(inbox).expanduser().resolve()),
        )
    return (
        sys.executable,
        "-m",
        "umml_manager.extractor_host",
        str(Path(project).expanduser().resolve()),
        str(Path(script).expanduser().resolve()),
        str(Path(inbox).expanduser().resolve()),
    )


def run_extractor(
    project: str | Path,
    script: str | Path,
    inbox: str | Path,
) -> int:
    """Run a recognized extractor source tree in this isolated process."""

    probe = runtime_probe()
    if not probe["ready"]:
        raise ExtractorHostError(
            "Werseter/umadump requires the bundled Python 3.14 runtime and "
            "minidump 0.0.24. Runtime probe: "
            + json.dumps(probe, sort_keys=True)
        )

    project_path = _regular_directory(project, "extractor project")
    script_path = _regular_file(script, "extractor entry point")
    try:
        script_path.relative_to(project_path)
    except ValueError as exc:
        raise ExtractorHostError(
            "Extractor entry point must be inside its project directory"
        ) from exc
    if script_path.parent != project_path or script_path.name != "main.py":
        raise ExtractorHostError(
            "Only the recognized Werseter project-root main.py may be hosted"
        )

    for name in WERSETER_REQUIRED:
        _regular_file(project_path / name, f"required extractor file {name}")
    _validate_requirements(project_path / "requirements.txt")

    inbox_path = _prepare_inbox(inbox)
    original_cwd = Path.cwd()
    original_argv = list(sys.argv)
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(project_path))
        os.chdir(inbox_path)
        sys.argv = [
            str(script_path),
            "--rerun-mode",
            "once",
            "--no-update-check",
        ]
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        sys.argv = original_argv
        sys.path[:] = original_path
        os.chdir(original_cwd)
    return 0


def _validate_requirements(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ExtractorHostError(
            f"Could not read extractor requirements: {path}: {exc}"
        ) from exc
    requirements = {
        "".join(line.split()).casefold()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }
    unsupported = sorted(requirements - SUPPORTED_REQUIREMENTS)
    if unsupported:
        raise ExtractorHostError(
            "This extractor declares dependencies not bundled by Uma Mod "
            "Manager: " + ", ".join(unsupported)
        )
    if not requirements:
        return
    if not any(item.startswith("minidump") for item in requirements):
        raise ExtractorHostError(
            "The recognized extractor requirements no longer declare minidump"
        )


def _regular_file(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ExtractorHostError(f"{label} is unavailable: {path}: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ExtractorHostError(f"{label} must be a regular file: {path}")
    return path


def _regular_directory(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ExtractorHostError(f"{label} is unavailable: {path}: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ExtractorHostError(f"{label} must be a regular directory: {path}")
    return path


def _prepare_inbox(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ExtractorHostError(
            f"Extractor inbox is unavailable: {path}: {exc}"
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ExtractorHostError(
            f"Extractor inbox must be a regular directory: {path}"
        )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="uma-mod-manager-extractor-host",
        description="Private isolated host for supported extractor source packages.",
    )
    parser.add_argument("project")
    parser.add_argument("script")
    parser.add_argument("inbox")
    args = parser.parse_args(argv)
    try:
        return run_extractor(args.project, args.script, args.inbox)
    except ExtractorHostError as exc:
        print(f"Extractor host error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

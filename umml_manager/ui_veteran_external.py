from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox


@dataclass(frozen=True)
class ExternalExtractorLaunch:
    command: tuple[str, ...]
    cwd: Path
    provider_hint: str


def build_external_launch(
    extractor: str | Path,
    inbox: str | Path,
    *,
    python_executable: str | None = None,
) -> ExternalExtractorLaunch:
    """Build a shell-free command for a user-selected external extractor.

    Werseter's source entry point imports sibling modules but writes relative
    output files. The bootstrap keeps the project directory importable while
    changing only the process working directory to UMML's isolated inbox.

    Frozen UMML packages must never use ``sys.executable`` as a Python
    interpreter: in that environment it points back to the Manager executable.
    A real system Python is selected explicitly instead.
    """

    path = Path(extractor).expanduser().resolve()
    output = Path(inbox).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"External extractor does not exist: {path}")
    output.mkdir(parents=True, exist_ok=True)

    if path.suffix.casefold() != ".py":
        return ExternalExtractorLaunch(
            command=(str(path),),
            cwd=output,
            provider_hint="standalone extractor",
        )

    werseter_source = _looks_like_werseter_source(path)
    python_command = _select_python_command(
        python_executable,
        requires_python_314=werseter_source,
    )
    if werseter_source:
        bootstrap = (
            "import os,runpy,sys; "
            "project,script,inbox=sys.argv[1:4]; "
            "sys.path.insert(0,project); "
            "os.chdir(inbox); "
            "sys.argv=[script,'--rerun-mode','once','--no-update-check']; "
            "runpy.run_path(script,run_name='__main__')"
        )
        return ExternalExtractorLaunch(
            command=(
                *python_command,
                "-c",
                bootstrap,
                str(path.parent),
                str(path),
                str(output),
            ),
            cwd=output,
            provider_hint="Werseter/umadump source",
        )

    return ExternalExtractorLaunch(
        command=(*python_command, str(path)),
        cwd=output,
        provider_hint="Python extractor",
    )


def launch_configured_extractor(app, page) -> None:
    configured = str(
        page.store.load_settings().get("extractor_path") or ""
    ).strip()
    if not configured:
        page.choose_extractor()
        configured = str(
            page.store.load_settings().get("extractor_path") or ""
        ).strip()
        if not configured:
            return

    try:
        launch = build_external_launch(configured, page.store.inbox)
    except (OSError, RuntimeError, ValueError) as exc:
        messagebox.showerror(
            "External extractor unavailable",
            str(exc),
            parent=app.root,
        )
        return

    if os.name != "nt":
        proceed = messagebox.askokcancel(
            "External process permissions",
            "UMML launches the selected tool without sudo or root privileges. "
            "Host ptrace/process-memory policy may still block it. Run the tool "
            "separately and import its JSON when elevation is required.\n\n"
            "Continue?",
            parent=app.root,
        )
        if not proceed:
            return

    log_path = page.store.inbox / "veteran-extractor.log"
    try:
        with log_path.open("ab") as log:
            subprocess.Popen(
                list(launch.command),
                cwd=launch.cwd,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
    except OSError as exc:
        messagebox.showerror(
            "Could not launch external extractor",
            str(exc),
            parent=app.root,
        )
        return

    app.status.set(
        f"Launched {launch.provider_hint}. Import latest output after it finishes."
    )


def _select_python_command(
    explicit: str | None,
    *,
    requires_python_314: bool,
) -> tuple[str, ...]:
    if explicit:
        return (explicit,)

    frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        if not requires_python_314 or sys.version_info >= (3, 14):
            return (sys.executable,)

    if os.name == "nt":
        launcher = shutil.which("py") or shutil.which("py.exe")
        if launcher:
            return (
                launcher,
                "-3.14" if requires_python_314 else "-3",
            )
        candidates = (
            ("python3.14.exe",) if requires_python_314 else ()
        ) + ("python.exe", "python3.exe")
    else:
        candidates = (
            ("python3.14",) if requires_python_314 else ()
        ) + ("python3", "python")

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            if requires_python_314 and candidate not in {
                "python3.14",
                "python3.14.exe",
            }:
                continue
            return (resolved,)

    requirement = "Python 3.14" if requires_python_314 else "Python 3"
    raise RuntimeError(
        f"{requirement} was not found for the selected source extractor. "
        "Install the required interpreter or choose the extractor's standalone "
        "executable release instead."
    )


def _looks_like_werseter_source(path: Path) -> bool:
    if path.name.casefold() != "main.py":
        return False
    required = ("memory.py", "json_encoders.py", "game_structs.py")
    return all((path.parent / name).is_file() for name in required)

from __future__ import annotations

import os
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

    python = python_executable or sys.executable
    if _looks_like_werseter_source(path):
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
                python,
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
        command=(python, str(path)),
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
    except (OSError, ValueError) as exc:
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


def _looks_like_werseter_source(path: Path) -> bool:
    if path.name.casefold() != "main.py":
        return False
    required = ("memory.py", "json_encoders.py", "game_structs.py")
    return all((path.parent / name).is_file() for name in required)

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox

from .extractor_packages import ManagedExtractor, install_extractor_archive


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
    changing only the process working directory to the Manager's isolated inbox.

    Frozen Manager packages must never use ``sys.executable`` as a Python
    interpreter: in that environment it points back to the Manager executable.
    A real external Python is selected explicitly instead.
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


def configure_external_extractor(app, page) -> None:
    """Select a program or install a recognized source ZIP as a managed tool."""

    selected = filedialog.askopenfilename(
        parent=app.root,
        title="Install or choose a Veteran roster extractor",
        filetypes=(
            ("Extractor package or program", "*.zip *.exe *.py"),
            ("Source ZIP", "*.zip"),
            ("Standalone executable", "*.exe"),
            ("Python source", "*.py"),
            ("All files", "*"),
        ),
    )
    if not selected:
        return
    path = Path(selected).expanduser().resolve()
    if path.suffix.casefold() != ".zip":
        _save_external_selection(page, path)
        app.status.set(f"External extractor selected: {path}")
        return

    proceed = messagebox.askokcancel(
        "Install external extractor source",
        "Uma Mod Manager will validate this ZIP, install it in an isolated "
        "Manager-owned tools directory, and create a private Python environment "
        "when Python 3.14 is available. Only dependencies declared by the "
        "package will be installed.\n\n"
        "The extractor reads the running game's memory and remains a separate "
        "upstream tool. Continue?",
        parent=app.root,
    )
    if not proceed:
        return

    tools_root = page.store.root / "tools"

    def completed(result: ManagedExtractor) -> None:
        settings = page.store.load_settings()
        settings.update(
            {
                "extractor_path": result.entrypoint,
                "extractor_python": result.python_executable,
                "extractor_package_root": result.install_root,
                "extractor_provider": result.provider,
                "extractor_version": result.version,
                "extractor_archive_sha256": result.archive_sha256,
            }
        )
        page.store.save_settings(settings)
        app.status.set(
            f"Installed {result.provider} {result.version}. "
            f"{result.runtime_message}"
        )
        messagebox.showinfo(
            "Extractor package installed",
            f"Installed {result.provider} {result.version}.\n\n"
            f"{result.runtime_message}\n\n"
            "Use Run extractor while the game is open on a compatible screen. "
            "Successful output will be imported automatically.",
            parent=app.root,
        )

    def failed(exc: Exception) -> None:
        app.status.set("External extractor installation failed")
        messagebox.showerror(
            "Could not install extractor ZIP",
            str(exc),
            parent=app.root,
        )

    app._run_task(
        "Validating and installing extractor source…",
        lambda: install_extractor_archive(path, tools_root),
        completed,
        failed=failed,
    )


def launch_configured_extractor(app, page) -> None:
    settings = page.store.load_settings()
    configured = str(settings.get("extractor_path") or "").strip()
    if not configured:
        configure_external_extractor(app, page)
        settings = page.store.load_settings()
        configured = str(settings.get("extractor_path") or "").strip()
        if not configured:
            return

    try:
        launch = build_external_launch(
            configured,
            page.store.inbox,
            python_executable=(
                str(settings.get("extractor_python") or "").strip()
                or None
            ),
        )
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
            "The Manager launches the selected tool without sudo or root "
            "privileges. Host ptrace/process-memory policy may still block it. "
            "Run the tool separately and import its JSON when elevation is "
            "required.\n\nContinue?",
            parent=app.root,
        )
        if not proceed:
            return

    log_path = page.store.inbox / "veteran-extractor.log"
    try:
        with log_path.open("ab") as log:
            process = subprocess.Popen(
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
        f"Running {launch.provider_hint}. "
        "Output will be imported when it finishes."
    )
    threading.Thread(
        target=_wait_for_extractor,
        args=(app, page, process, launch.provider_hint, log_path),
        name=f"uma-extractor-wait-{process.pid}",
        daemon=True,
    ).start()


def _wait_for_extractor(
    app,
    page,
    process,
    provider_hint: str,
    log_path: Path,
) -> None:
    return_code = process.wait()

    def completed() -> None:
        if return_code != 0:
            app.status.set(
                f"{provider_hint} exited with code {return_code}. "
                f"See {log_path.name}."
            )
            return
        candidates = [
            path
            for path in page.store.inbox.glob("*.json")
            if path.is_file()
        ]
        if not candidates:
            app.status.set(
                f"{provider_hint} finished but produced no JSON roster. "
                f"See {log_path.name}."
            )
            return
        app.status.set(
            f"{provider_hint} finished; importing its latest output…"
        )
        page.import_latest_output()

    try:
        app.root.after(0, completed)
    except Exception:
        return


def _save_external_selection(page, path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(
            f"External extractor does not exist: {path}"
        )
    settings = page.store.load_settings()
    settings.update(
        {
            "extractor_path": str(path),
            "extractor_python": "",
            "extractor_package_root": "",
            "extractor_provider": "user-selected external tool",
            "extractor_version": "",
            "extractor_archive_sha256": "",
        }
    )
    page.store.save_settings(settings)


def _select_python_command(
    explicit: str | None,
    *,
    requires_python_314: bool,
) -> tuple[str, ...]:
    if explicit:
        resolved = Path(explicit).expanduser().resolve()
        if not resolved.is_file():
            raise RuntimeError(
                f"Configured extractor Python is missing: {resolved}"
            )
        return (str(resolved),)

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
        "Select the source ZIP again after installing it, or choose the "
        "extractor's standalone executable release instead."
    )


def _looks_like_werseter_source(path: Path) -> bool:
    if path.name.casefold() != "main.py":
        return False
    required = ("memory.py", "json_encoders.py", "game_structs.py")
    return all((path.parent / name).is_file() for name in required)

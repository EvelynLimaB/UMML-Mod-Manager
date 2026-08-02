from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import BinaryIO

from .extractor_host import packaged_host_available, packaged_host_command
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

    Supported packaged builds run Werseter source through a private Python 3.14
    host in a separate Manager process. Source/development installations retain
    the explicit external-interpreter path. In both cases the upstream source
    stays outside the Manager process and writes only to the isolated inbox.
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
    if (
        werseter_source
        and not python_executable
        and bool(getattr(sys, "frozen", False))
        and packaged_host_available()
    ):
        return ExternalExtractorLaunch(
            command=packaged_host_command(path.parent, path, output),
            cwd=output,
            provider_hint="Werseter/umadump bundled runtime",
        )

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
        try:
            _save_external_selection(page, path)
        except (OSError, RuntimeError) as exc:
            messagebox.showerror(
                "External extractor unavailable",
                str(exc),
                parent=app.root,
            )
            return
        app.status.set(f"External extractor selected: {path}")
        return

    bundled_runtime = bool(
        getattr(sys, "frozen", False) and packaged_host_available()
    )
    runtime_description = (
        "use the Python 3.14 runtime bundled with this application"
        if bundled_runtime
        else "create a private Python environment when Python 3.14 is available"
    )
    proceed = messagebox.askokcancel(
        "Install external extractor source",
        "Uma Mod Manager will validate this ZIP, install it in an isolated "
        "Manager-owned tools directory, and "
        + runtime_description
        + ". Only the supported dependency declared by the package is used.\n\n"
        "The extractor reads the running game's memory and remains a separate "
        "upstream tool. Continue?",
        parent=app.root,
    )
    if not proceed:
        return

    tools_root = page.store.root / "tools"

    def completed(result: ManagedExtractor) -> None:
        runtime_message = (
            "Bundled Python 3.14 extractor runtime ready."
            if bundled_runtime
            else result.runtime_message
        )
        settings = page.store.load_settings()
        settings.update(
            {
                "extractor_path": result.entrypoint,
                "extractor_python": (
                    "" if bundled_runtime else result.python_executable
                ),
                "extractor_runtime": (
                    "bundled-host" if bundled_runtime else "external-python"
                ),
                "extractor_package_root": result.install_root,
                "extractor_provider": result.provider,
                "extractor_version": result.version,
                "extractor_archive_sha256": result.archive_sha256,
            }
        )
        page.store.save_settings(settings)
        app.status.set(
            f"Installed {result.provider} {result.version}. {runtime_message}"
        )
        messagebox.showinfo(
            "Extractor package installed",
            f"Installed {result.provider} {result.version}.\n\n"
            f"{runtime_message}\n\n"
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
        lambda: install_extractor_archive(
            path,
            tools_root,
            create_runtime=not bundled_runtime,
        ),
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

    configured_python = (
        str(settings.get("extractor_python") or "").strip() or None
    )
    if (
        _looks_like_werseter_source(Path(configured).expanduser().resolve())
        and bool(getattr(sys, "frozen", False))
        and packaged_host_available()
    ):
        # Automatically upgrade alpha20 installations whose source was already
        # installed before the standalone runtime existed.
        configured_python = None
        if settings.get("extractor_runtime") != "bundled-host":
            settings["extractor_runtime"] = "bundled-host"
            settings["extractor_python"] = ""
            page.store.save_settings(settings)
            app.status.set("Upgraded the installed extractor to the bundled runtime")

    try:
        launch = build_external_launch(
            configured,
            page.store.inbox,
            python_executable=configured_python,
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
        log = _open_extractor_log(log_path)
        try:
            process = subprocess.Popen(
                list(launch.command),
                cwd=launch.cwd,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
        finally:
            log.close()
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
            if _regular_file(path)
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


def _open_extractor_log(path: Path) -> BinaryIO:
    """Open the Manager-owned extractor log without following a planted link."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        flags |= nofollow
    descriptor = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("Extractor log destination is not a regular file")
        if not nofollow:
            # Windows lacks O_NOFOLLOW. Compare the path entry itself after open
            # and reject reparse/symlink-style links before handing it to Popen.
            try:
                if stat.S_ISLNK(path.lstat().st_mode):
                    raise OSError("Extractor log destination cannot be a symlink")
            except OSError:
                raise
        return os.fdopen(descriptor, "ab", closefd=True)
    except Exception:
        os.close(descriptor)
        raise


def _regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _save_external_selection(page, path: Path) -> None:
    if not _regular_file(path):
        raise FileNotFoundError(
            f"External extractor must be a regular non-symlink file: {path}"
        )
    settings = page.store.load_settings()
    settings.update(
        {
            "extractor_path": str(path),
            "extractor_python": "",
            "extractor_runtime": "external",
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
        command = (str(resolved),)
        if requires_python_314 and not _python_command_is_314(command):
            raise RuntimeError(
                f"Configured extractor Python is older than 3.14: {resolved}"
            )
        return command

    frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        if not requires_python_314 or sys.version_info >= (3, 14):
            return (sys.executable,)

    commands: list[tuple[str, ...]] = []
    if os.name == "nt":
        launcher = shutil.which("py") or shutil.which("py.exe")
        if launcher:
            commands.append(
                (launcher, "-3.14" if requires_python_314 else "-3")
            )
        names = (
            "python3.14.exe",
            "python.exe",
            "python3.exe",
        )
    else:
        names = ("python3.14", "python3", "python")
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            commands.append((resolved,))

    for command in commands:
        if not requires_python_314 or _python_command_is_314(command):
            return command

    requirement = "Python 3.14" if requires_python_314 else "Python 3"
    raise RuntimeError(
        f"{requirement} was not found for the selected source extractor. "
        "Use a standalone Uma Mod Manager build with the bundled extractor "
        "runtime, or choose the extractor's standalone executable release."
    )


def _python_command_is_314(command: tuple[str, ...]) -> bool:
    try:
        result = subprocess.run(
            (
                *command,
                "-c",
                "import sys;print(int(sys.version_info >= (3,14)))",
            ),
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.stdout.strip() == "1"


def _looks_like_werseter_source(path: Path) -> bool:
    if path.name.casefold() != "main.py":
        return False
    required = ("memory.py", "json_encoders.py", "game_structs.py")
    return all((path.parent / name).is_file() for name in required)

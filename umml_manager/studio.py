from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class LegacyTool:
    id: str
    name: str
    description: str
    method: str | None = None
    mutating: bool = True


LEGACY_TOOLS: tuple[LegacyTool, ...] = (
    LegacyTool(
        "full",
        "Full legacy workspace",
        "Every original loader action and editor in one compatibility window.",
    ),
    LegacyTool(
        "attributes",
        "Character attributes",
        "Edit character body and presentation attributes.",
        "open_chara_settings",
    ),
    LegacyTool(
        "personality",
        "Character personality",
        "Edit personality and character behavior data.",
        "open_personality_settings",
    ),
    LegacyTool(
        "dress",
        "Dress editor",
        "Inspect and edit dress assignments and colors.",
        "open_dress_settings",
    ),
    LegacyTool(
        "training",
        "Training editor",
        "Edit Single Mode training data.",
        "open_training_settings",
    ),
    LegacyTool(
        "concert",
        "Story & concert",
        "Add, edit, and restore story concert setups.",
        "open_story_concert",
    ),
    LegacyTool(
        "swap",
        "Character / model swap",
        "Swap body, head, tail, attributes, and chibi components.",
        "open_swap_character",
    ),
    LegacyTool(
        "translation",
        "Translation merge",
        "Merge Global text into the Japanese client.",
        "force_translate_english",
    ),
    LegacyTool(
        "cleanup",
        "Clean unused assets",
        "Run the original unused-asset cleanup tool.",
        "clean_unused_assets",
    ),
    LegacyTool(
        "database",
        "Database reset",
        "Delete master.mdb so the game downloads a clean copy.",
        "delete_master_db",
    ),
)


class OpenPathError(RuntimeError):
    """Raised when the desktop cannot open a Manager-owned path."""


class LegacyToolLauncher:
    def launch(
        self,
        tool_id: str = "full",
        *,
        dat_path: str = "",
        game_dir: str = "",
        meta_path: str = "",
        region: str = "",
    ) -> subprocess.Popen:
        tool = next((item for item in LEGACY_TOOLS if item.id == tool_id), None)
        if tool is None:
            raise ValueError(f"Unknown legacy tool: {tool_id}")
        env = os.environ.copy()
        dat = Path(dat_path).expanduser() if dat_path else None
        if dat:
            persistent = dat.parent if dat.name.casefold() == "dat" else dat
            env["UMML_PERSISTENT_DIR"] = str(persistent)
        if game_dir:
            env["UMML_GAME_DIR"] = str(Path(game_dir).expanduser())
        if meta_path:
            env["UMML_MANAGER_META_PATH"] = str(Path(meta_path).expanduser())
        if region:
            env["UMML_MANAGER_REGION"] = region
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--legacy-host"]
        else:
            command = [sys.executable, "-m", "umml_manager.legacy_host"]
        if tool.method:
            command += ["--tool", tool.method]
        return subprocess.Popen(command, env=env)


def external_process_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment safe for launching host desktop applications.

    PyInstaller temporarily prepends its private runtime to LD_LIBRARY_PATH. That
    is required when launching another bundled UMML entry point, but it can make
    host tools such as xdg-open, gio, and Dolphin load incompatible bundled
    libraries and exit before opening anything. Restore the host value for
    commands that deliberately leave the Manager process.
    """

    env = dict(os.environ if source is None else source)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original is None:
        env.pop("LD_LIBRARY_PATH", None)
    else:
        env["LD_LIBRARY_PATH"] = original
    return env


def open_path(path: str | Path) -> None:
    requested = Path(path).expanduser()
    try:
        target = requested.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise OpenPathError(f"Path does not exist or cannot be resolved: {requested}") from exc

    if sys.platform.startswith("win"):
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except OSError as exc:
            raise OpenPathError(f"Windows could not open: {target}") from exc
        return

    env = external_process_environment()
    if sys.platform == "darwin":
        _run_open_command(("open", str(target)), env=env, label="open")
        return

    _open_linux_path(target, env=env)


def _open_linux_path(target: Path, *, env: Mapping[str, str]) -> None:
    uri = target.as_uri()
    desktop = " ".join(
        (
            env.get("XDG_CURRENT_DESKTOP", ""),
            env.get("XDG_SESSION_DESKTOP", ""),
            env.get("DESKTOP_SESSION", ""),
        )
    ).casefold()

    kde_commands = (
        ("kioclient6", "exec", uri),
        ("kioclient5", "exec", uri),
        ("kioclient", "exec", uri),
    )
    generic_commands = (
        ("gio", "open", uri),
        ("xdg-open", str(target)),
    )
    commands = (
        (*kde_commands, *generic_commands)
        if "kde" in desktop or "plasma" in desktop
        else (*generic_commands, *kde_commands)
    )

    failures: list[str] = []
    for command in commands:
        executable = shutil.which(command[0], path=env.get("PATH"))
        if not executable:
            continue
        try:
            _run_open_command(
                (executable, *command[1:]),
                env=env,
                label=command[0],
            )
            return
        except OpenPathError as exc:
            failures.append(str(exc))

    # A direct file-manager fallback matters on immutable KDE systems where
    # xdg-open may be installed but its desktop helper is missing or broken.
    if target.is_dir():
        direct_commands = (
            ("dolphin", "--new-window", str(target)),
            ("nautilus", "--new-window", str(target)),
            ("nemo", str(target)),
            ("thunar", str(target)),
            ("pcmanfm", str(target)),
        )
        for command in direct_commands:
            executable = shutil.which(command[0], path=env.get("PATH"))
            if not executable:
                continue
            try:
                process = subprocess.Popen(
                    (executable, *command[1:]),
                    env=dict(env),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                try:
                    return_code = process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    return
                if return_code == 0:
                    return
                failures.append(f"{command[0]} exited with status {return_code}")
            except OSError as exc:
                failures.append(f"{command[0]} could not start: {exc}")

    detail = "; ".join(failures[-4:]) if failures else "no supported desktop opener was found"
    raise OpenPathError(f"Could not open {target}. {detail}")


def _run_open_command(
    command: tuple[str, ...],
    *,
    env: Mapping[str, str],
    label: str,
) -> None:
    try:
        completed = subprocess.run(
            command,
            env=dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise OpenPathError(f"{label} timed out") from exc
    except OSError as exc:
        raise OpenPathError(f"{label} could not start: {exc}") from exc

    if completed.returncode == 0:
        return
    detail = (completed.stderr or completed.stdout or "").strip().replace("\n", " ")
    if len(detail) > 240:
        detail = detail[:237] + "..."
    suffix = f": {detail}" if detail else ""
    raise OpenPathError(f"{label} exited with status {completed.returncode}{suffix}")

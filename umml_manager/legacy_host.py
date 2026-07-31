from __future__ import annotations

import argparse
import functools
import os
import tkinter as tk
from tkinter import messagebox

from .process import running_game_processes

_MUTATING_METHODS = {
    "load_assets",
    "load_assets_manual",
    "restore_original_assets",
    "unload_assets",
    "clean_unused_assets",
    "delete_master_db",
    "force_translate_english",
    "open_chara_settings",
    "open_personality_settings",
    "open_dress_settings",
    "open_training_settings",
    "open_story_concert",
    "open_swap_character",
}


def _running_game(gui) -> tuple:
    game_dir = getattr(gui, "game_dir", "") or os.environ.get("UMML_GAME_DIR", "")
    return running_game_processes(game_dir or None)


def _inspection_failure_message(exc: Exception) -> str:
    return (
        "UMML could not verify whether Umamusume is running. Legacy Studio writes "
        "are blocked until process inspection works again.\n\n"
        f"Process inspection error: {exc}"
    )


def _install_guard(cls) -> None:
    for name in _MUTATING_METHODS:
        original = getattr(cls, name, None)
        if original is None or getattr(original, "_umml_manager_guarded", False):
            continue

        @functools.wraps(original)
        def guarded(self, *args, __original=original, __name=name, **kwargs):
            try:
                running = _running_game(self)
            except Exception as exc:
                messagebox.showerror(
                    "Process inspection unavailable",
                    _inspection_failure_message(exc),
                    parent=getattr(self, "root", None),
                )
                return None
            if running:
                names = ", ".join(sorted({item.name for item in running}))
                messagebox.showwarning(
                    "Close the game first",
                    f"{__name.replace('_', ' ').title()} can change game data.\n\n"
                    f"Detected running process: {names}\n\nClose Umamusume and try again.",
                    parent=getattr(self, "root", None),
                )
                return None
            return __original(self, *args, **kwargs)

        guarded._umml_manager_guarded = True  # type: ignore[attr-defined]
        setattr(cls, name, guarded)


def _watch_game(root: tk.Tk, gui) -> None:
    if not root.winfo_exists():
        return
    try:
        running = _running_game(gui)
    except Exception as exc:
        messagebox.showerror(
            "Studio closed for safety",
            _inspection_failure_message(exc)
            + "\n\nThe compatibility Studio will now close.",
            parent=root,
        )
        root.destroy()
        return
    if running:
        names = ", ".join(sorted({item.name for item in running}))
        messagebox.showwarning(
            "Studio closed for safety",
            "Umamusume started while the legacy Studio was open. The Studio will now "
            "close so nested legacy editor callbacks cannot write while the game is running.\n\n"
            f"Detected process: {names}",
            parent=root,
        )
        root.destroy()
        return
    root.after(750, lambda: _watch_game(root, gui))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UMML Manager legacy-tool compatibility host"
    )
    parser.add_argument("--tool", default="")
    args = parser.parse_args(argv)

    import UMML as application

    _install_guard(application.ModLoaderGUI)
    root = tk.Tk()
    gui = application.ModLoaderGUI(root)
    root.title("UMML Studio — Legacy compatibility tools")
    root.after(250, lambda: _watch_game(root, gui))

    if args.tool:
        method = getattr(gui, args.tool, None)
        if not callable(method):
            messagebox.showerror(
                "Tool unavailable",
                f"Legacy tool is unavailable: {args.tool}",
                parent=root,
            )
        else:
            root.after(150, method)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

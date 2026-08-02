from __future__ import annotations

import tkinter as tk

from .ui_veteran_external import (
    configure_external_extractor,
    launch_configured_extractor,
)
from .ui_veteran_presenter_v2 import VeteranRosterPage
from .ui_veteran_providers import launch_provider_window
from .ui_windows import present_toplevel


def veteran_window_geometry(window: tk.Toplevel) -> str:
    """Return a large centered fallback geometry for window managers without zoom."""

    try:
        screen_width = int(window.winfo_vrootwidth() or window.winfo_screenwidth())
        screen_height = int(window.winfo_vrootheight() or window.winfo_screenheight())
        origin_x = int(window.winfo_vrootx())
        origin_y = int(window.winfo_vrooty())
    except (tk.TclError, TypeError, ValueError):
        screen_width, screen_height = 1440, 900
        origin_x = origin_y = 0

    screen_width = max(1020, screen_width)
    screen_height = max(680, screen_height)
    horizontal_margin = max(16, min(36, screen_width // 60))
    vertical_margin = max(24, min(48, screen_height // 24))
    width = max(1020, screen_width - horizontal_margin * 2)
    height = max(680, screen_height - vertical_margin * 2)
    x = origin_x + max(0, (screen_width - width) // 2)
    y = origin_y + max(0, (screen_height - height) // 2)
    return f"{width}x{height}+{x}+{y}"


def maximize_veteran_window(window: tk.Toplevel) -> None:
    """Ask the native window manager to maximize, retaining geometry as fallback."""

    try:
        windowing_system = str(window.tk.call("tk", "windowingsystem"))
    except tk.TclError:
        windowing_system = ""
    try:
        if windowing_system == "x11":
            window.attributes("-zoomed", True)
        else:
            window.state("zoomed")
    except tk.TclError:
        # Some lightweight window managers expose neither operation. The large
        # centered geometry above still uses almost all available screen space.
        pass


def launch_veterans_window(app) -> None:
    existing = getattr(app, "_veterans_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                present_toplevel(existing, app.root)
                maximize_veteran_window(existing)
                return
        except tk.TclError:
            pass

    window = tk.Toplevel(app.root)
    app._veterans_window = window
    window.title("Uma Mod Manager · Veteran Roster")
    window.geometry(veteran_window_geometry(window))
    window.minsize(1020, 680)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(0, weight=1)

    page = VeteranRosterPage(window, app)
    page.configure_workspace_rows()
    page.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
    page.import_button.configure(text="Import roster JSON")
    page.choose_extractor_button.configure(
        text="Install or choose extractor",
        command=lambda: configure_external_extractor(app, page),
    )
    page.run_extractor_button.configure(
        command=lambda: launch_configured_extractor(app, page)
    )
    page.open_upstream_button.configure(
        text="Extractor projects",
        command=lambda: launch_provider_window(app),
    )
    page.notice_value.set(
        "Choose a downloaded source ZIP, standalone executable, or script. "
        "Recognized Werseter source ZIPs are validated and installed into an "
        "isolated Manager-owned directory. Standalone packages run supported "
        "source through the bundled Python 3.14 host, so no system Python is "
        "required. The Manager imports scrubbed output but does not bundle "
        "upstream scanner code."
    )

    def close() -> None:
        app._veterans_window = None
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.bind("<Escape>", lambda _event: close())
    present_toplevel(window, app.root)
    window.after_idle(lambda: maximize_veteran_window(window))

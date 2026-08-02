from __future__ import annotations

import tkinter as tk

from .ui_veteran_external import (
    configure_external_extractor,
    launch_configured_extractor,
)
from .ui_veteran_providers import launch_provider_window
from .ui_veterans import VeteransPage
from .ui_windows import present_toplevel


def launch_veterans_window(app) -> None:
    existing = getattr(app, "_veterans_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                present_toplevel(existing, app.root)
                return
        except tk.TclError:
            pass

    window = tk.Toplevel(app.root)
    app._veterans_window = window
    window.title("Uma Mod Manager · Veteran Roster")
    window.geometry("1240x780")
    window.minsize(980, 640)
    window.transient(app.root)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(0, weight=1)

    page = VeteransPage(window, app)
    page.rowconfigure(2, weight=0)
    page.rowconfigure(3, weight=1)
    page.grid(row=0, column=0, sticky="nsew", padx=18, pady=16)
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

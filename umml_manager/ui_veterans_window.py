from __future__ import annotations

import tkinter as tk

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
    window.title("UMML Veteran Roster")
    window.geometry("1240x780")
    window.minsize(980, 640)
    window.transient(app.root)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(0, weight=1)

    page = VeteransPage(window, app)
    page.grid(row=0, column=0, sticky="nsew", padx=18, pady=16)

    def close() -> None:
        app._veterans_window = None
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.bind("<Escape>", lambda _event: close())
    present_toplevel(window, app.root)

from __future__ import annotations

import tkinter as tk
import webbrowser
from dataclasses import dataclass
from tkinter import ttk

from .ui_windows import present_toplevel


@dataclass(frozen=True)
class VeteranProvider:
    name: str
    url: str
    output: str
    description: str


PROVIDERS = (
    VeteranProvider(
        name="rockisch/umadump",
        url="https://github.com/rockisch/umadump",
        output="Classic data.json",
        description=(
            "Original public umadump project. It established the community JSON "
            "roster format and remains the correct lineage credit."
        ),
    ),
    VeteranProvider(
        name="NECOtype/UmaExtractor",
        url="https://github.com/NECOtype/UmaExtractor",
        output="Classic-compatible data.json",
        description=(
            "Updated roster-focused fork with more resilient extraction and a "
            "standalone Windows workflow."
        ),
    ),
    VeteranProvider(
        name="Werseter/umadump 2.0",
        url="https://github.com/Werseter/umadump",
        output="trained_chara_data.json",
        description=(
            "Modern IL2CPP runtime reader with schema validation, live/minidump "
            "backends, and additional support-card, card, friend, trophy, replay, "
            "and training-state outputs."
        ),
    ),
)


def launch_provider_window(app) -> None:
    existing = getattr(app, "_veteran_providers_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                present_toplevel(existing, app.root)
                return
        except tk.TclError:
            pass

    window = tk.Toplevel(app.root)
    app._veteran_providers_window = window
    window.title("Veteran extractor projects")
    window.geometry("760x560")
    window.minsize(660, 500)
    window.transient(app.root)
    window.columnconfigure(0, weight=1)
    window.rowconfigure(1, weight=1)

    intro = ttk.Frame(window, padding=(18, 16, 18, 8))
    intro.grid(row=0, column=0, sticky="ew")
    intro.columnconfigure(0, weight=1)
    ttk.Label(
        intro,
        text="External veteran-roster providers",
        style="PageTitle.TLabel",
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        intro,
        text=(
            "UMML imports validated JSON from these projects. It does not bundle "
            "their scanners or binaries because their repository roots do not "
            "currently declare a project-wide license."
        ),
        style="Muted.TLabel",
        wraplength=700,
        justify="left",
    ).grid(row=1, column=0, sticky="ew", pady=(5, 0))

    cards = ttk.Frame(window, padding=(18, 4, 18, 12))
    cards.grid(row=1, column=0, sticky="nsew")
    cards.columnconfigure(0, weight=1)
    for index, provider in enumerate(PROVIDERS):
        card = ttk.Frame(cards, style="Surface.TFrame", padding=14)
        card.grid(row=index, column=0, sticky="ew", pady=5)
        card.columnconfigure(0, weight=1)
        ttk.Label(
            card,
            text=provider.name,
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            card,
            text=f"Roster output: {provider.output}",
            style="SurfaceMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Label(
            card,
            text=provider.description,
            style="SurfaceMuted.TLabel",
            wraplength=590,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(
            card,
            text="Open original project",
            command=lambda url=provider.url: webbrowser.open(url, new=2),
        ).grid(row=0, column=1, rowspan=3, sticky="e", padx=(14, 0))

    footer = ttk.Frame(window, padding=(18, 0, 18, 16))
    footer.grid(row=2, column=0, sticky="ew")
    footer.columnconfigure(0, weight=1)
    ttk.Label(
        footer,
        text=(
            "Choose or run any extractor yourself, then import data.json or "
            "trained_chara_data.json in the Veteran roster workspace."
        ),
        style="Muted.TLabel",
        wraplength=600,
        justify="left",
    ).grid(row=0, column=0, sticky="w")

    def close() -> None:
        app._veteran_providers_window = None
        window.destroy()

    ttk.Button(footer, text="Close", command=close).grid(
        row=0,
        column=1,
        sticky="e",
        padx=(12, 0),
    )
    window.protocol("WM_DELETE_WINDOW", close)
    window.bind("<Escape>", lambda _event: close())
    present_toplevel(window, app.root)

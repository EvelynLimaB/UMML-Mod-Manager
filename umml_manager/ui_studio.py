from __future__ import annotations

from tkinter import ttk

from .studio import LEGACY_TOOLS
from .ui_veterans_window import launch_veterans_window


class StudioPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.tool_buttons = {}
        self.tool_mutating = {}
        self.columnconfigure(0, weight=1)
        ttk.Label(
            self,
            text=(
                "Read-only analysis tools may run while the game is open. Legacy editing features "
                "remain available through the compatibility Studio, but that host requires the game "
                "to be closed because it still contains mutating callbacks."
            ),
            style="Muted.TLabel",
            wraplength=850,
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))
        cards = ttk.Frame(self)
        cards.grid(row=1, column=0, sticky="nsew")
        for column in range(2):
            cards.columnconfigure(column, weight=1)

        veteran_card = ttk.Frame(cards, style="Surface.TFrame", padding=15)
        veteran_card.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=6)
        veteran_card.columnconfigure(0, weight=1)
        ttk.Label(
            veteran_card,
            text="Veteran roster",
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            veteran_card,
            text=(
                "Import and browse UmaExtractor data.json snapshots, filter veterans, inspect stats, "
                "skills, factors and aptitudes, and export scrubbed local data. The external extractor "
                "is credited and launched separately; no unlicensed upstream code is bundled."
            ),
            style="SurfaceMuted.TLabel",
            wraplength=380,
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))
        veteran_button = ttk.Button(
            veteran_card,
            text="Open",
            style="Accent.TButton",
            command=lambda: launch_veterans_window(app),
        )
        veteran_button.grid(row=2, column=0, sticky="w")
        self.tool_buttons["veterans"] = veteran_button
        self.tool_mutating["veterans"] = False

        for index, tool in enumerate(LEGACY_TOOLS, start=1):
            card = ttk.Frame(cards, style="Surface.TFrame", padding=15)
            card.grid(
                row=index // 2,
                column=index % 2,
                sticky="nsew",
                padx=(0 if index % 2 == 0 else 7, 7 if index % 2 == 0 else 0),
                pady=6,
            )
            card.columnconfigure(0, weight=1)
            ttk.Label(card, text=tool.name, style="CardTitle.TLabel").grid(
                row=0, column=0, sticky="w"
            )
            ttk.Label(
                card,
                text=tool.description,
                style="SurfaceMuted.TLabel",
                wraplength=380,
            ).grid(row=1, column=0, sticky="w", pady=(4, 10))
            button = ttk.Button(
                card,
                text="Open",
                style="Accent.TButton" if tool.id == "full" else "TButton",
                command=lambda item=tool: app.launch_legacy_tool(item.id),
            )
            button.grid(row=2, column=0, sticky="w")
            self.tool_buttons[tool.id] = button
            # Every legacy card launches the same compatibility host. Its lifetime watcher
            # closes the entire host when Umamusume runs, including the full workspace.
            self.tool_mutating[tool.id] = True

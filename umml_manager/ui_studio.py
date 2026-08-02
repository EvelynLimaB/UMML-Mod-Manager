from __future__ import annotations

from tkinter import ttk

from .studio import LEGACY_TOOLS
from .ui_scrollable import ScrollablePage, responsive_columns
from .ui_veterans_window import launch_veterans_window


class StudioPage(ScrollablePage):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.tool_buttons = {}
        self.tool_mutating = {}
        self._legacy_cards: list[tuple[ttk.Frame, ttk.Label]] = []
        page = self.content
        page.columnconfigure(0, weight=1)

        self.introduction = ttk.Label(
            page,
            text=(
                "Read-only analysis tools may run while the game is open. Legacy editing "
                "features remain available through the compatibility Studio, but that host "
                "requires the game to be closed because it still contains mutating callbacks."
            ),
            style="Muted.TLabel",
            justify="left",
        )
        self.introduction.grid(row=0, column=0, sticky="w", pady=(0, 14))

        ttk.Label(
            page,
            text="Read-only tools",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(
            page,
            text="These tools inspect or import local data without changing game files.",
            style="Muted.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(2, 7))

        self.veteran_card = ttk.Frame(page, style="Surface.TFrame", padding=15)
        self.veteran_card.grid(row=3, column=0, sticky="ew", pady=(0, 16))
        self.veteran_card.columnconfigure(0, weight=1)
        veteran_title = ttk.Frame(self.veteran_card, style="Surface.TFrame")
        veteran_title.grid(row=0, column=0, sticky="ew")
        veteran_title.columnconfigure(0, weight=1)
        ttk.Label(
            veteran_title,
            text="Veteran roster",
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            veteran_title,
            text="Read-only",
            style="Good.Badge.TLabel",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.veteran_description = ttk.Label(
            self.veteran_card,
            text=(
                "Import and browse UmaExtractor data.json snapshots, filter veterans, inspect "
                "stats, skills, factors and aptitudes, and export scrubbed local data. The "
                "external extractor is credited and launched separately; no unlicensed upstream "
                "code is bundled."
            ),
            style="SurfaceMuted.TLabel",
            justify="left",
        )
        self.veteran_description.grid(row=1, column=0, sticky="w", pady=(6, 10))
        veteran_button = ttk.Button(
            self.veteran_card,
            text="Open",
            style="Accent.TButton",
            command=lambda: launch_veterans_window(app),
        )
        veteran_button.grid(row=2, column=0, sticky="w")
        self.tool_buttons["veterans"] = veteran_button
        self.tool_mutating["veterans"] = False

        ttk.Separator(page).grid(row=4, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(
            page,
            text="Compatibility Studio",
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=5, column=0, sticky="w")
        self.legacy_explanation = ttk.Label(
            page,
            text=(
                "These cards launch the original UMML compatibility host. They remain available "
                "for creator workflows, but every host is closed or disabled while Umamusume is "
                "running so legacy callbacks cannot mutate live game data."
            ),
            style="Muted.TLabel",
            justify="left",
        )
        self.legacy_explanation.grid(row=6, column=0, sticky="w", pady=(2, 8))

        self.cards = ttk.Frame(page)
        self.cards.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        self.cards.columnconfigure(0, weight=1)
        self.cards.columnconfigure(1, weight=1)

        for index, tool in enumerate(LEGACY_TOOLS):
            card = ttk.Frame(self.cards, style="Surface.TFrame", padding=15)
            card.columnconfigure(0, weight=1)
            title = ttk.Frame(card, style="Surface.TFrame")
            title.grid(row=0, column=0, sticky="ew")
            title.columnconfigure(0, weight=1)
            ttk.Label(title, text=tool.name, style="CardTitle.TLabel").grid(
                row=0,
                column=0,
                sticky="w",
            )
            ttk.Label(
                title,
                text="Close game first",
                style="Warning.Badge.TLabel",
            ).grid(row=0, column=1, sticky="e", padx=(12, 0))
            description = ttk.Label(
                card,
                text=tool.description,
                style="SurfaceMuted.TLabel",
                justify="left",
            )
            description.grid(row=1, column=0, sticky="w", pady=(6, 10))
            button = ttk.Button(
                card,
                text="Open",
                style="Accent.TButton" if tool.id == "full" else "TButton",
                command=lambda item=tool: app.launch_legacy_tool(item.id),
            )
            button.grid(row=2, column=0, sticky="w")
            self.tool_buttons[tool.id] = button
            # Every legacy card launches the same compatibility host. Its lifetime
            # watcher closes the whole host when Umamusume runs, including tools
            # whose first screen appears read-only.
            self.tool_mutating[tool.id] = True
            self._legacy_cards.append((card, description))

        self.set_resize_callback(self._reflow)
        self.finalize_scroll_bindings()

    def _reflow(self, width: int) -> None:
        full_wrap = max(280, width - 36)
        self.introduction.configure(wraplength=full_wrap)
        self.veteran_description.configure(wraplength=max(280, width - 64))
        self.legacy_explanation.configure(wraplength=full_wrap)

        columns = responsive_columns(width, breakpoint=840)
        self.cards.columnconfigure(0, weight=1)
        self.cards.columnconfigure(1, weight=1 if columns == 2 else 0)
        card_wrap = max(250, int((width - (18 if columns == 2 else 0)) / columns) - 54)
        for index, (card, description) in enumerate(self._legacy_cards):
            card.grid_forget()
            column = index % columns
            row = index // columns
            if columns == 1:
                padx = 0
            elif column == 0:
                padx = (0, 7)
            else:
                padx = (7, 0)
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=padx,
                pady=6,
            )
            description.configure(wraplength=card_wrap)

from __future__ import annotations

from tkinter import ttk

from .ui_veteran_lab import RosterLabPage


class VeteranRosterPage(RosterLabPage):
    """Final responsive roster workspace used by the standalone window.

    The underlying lab owns the data tools. This thin presentation layer keeps
    the action area and metric cards usable at the roster window's minimum size.
    """

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._compact_selected_actions()

    def _compact_selected_actions(self) -> None:
        bar = self.copy_ids_button.master
        for column in range(3):
            bar.columnconfigure(column, weight=1, uniform="roster-action")

        self.same_character_button.configure(text="This character")
        self.export_selected_button.configure(text="Export JSON")
        self.copy_ids_button.configure(text="Copy IDs")
        self.same_character_button.grid_configure(row=1, column=0, padx=(0, 4))
        self.export_selected_button.grid_configure(row=1, column=1, padx=4)
        self.copy_ids_button.grid_configure(
            row=1,
            column=2,
            sticky="ew",
            padx=(4, 0),
            pady=(6, 0),
        )

        # The selected pin is already visible through the button style and the
        # highlighted roster row. A third action row repeating its name only
        # consumed the detail viewport at compact heights.
        for child in bar.winfo_children():
            try:
                if str(child.cget("textvariable")) == str(self.pin_status_value):
                    child.grid_remove()
            except (AttributeError, TypeError):
                continue

    def _layout_metrics(self, width: int) -> None:
        self._layout_after = None
        columns = 3 if width < 1080 else 5
        if columns == self._metrics_columns:
            return

        # Reset stale grid weights when crossing the breakpoint. Without this,
        # switching from five cards to three left two invisible columns sharing
        # the available width, making the visible cards look oddly compressed.
        for column in range(5):
            self.metrics.columnconfigure(column, weight=0, uniform="")
        for card in self.metric_cards:
            card.grid_forget()

        self._metrics_columns = columns
        for column in range(columns):
            self.metrics.columnconfigure(
                column,
                weight=1,
                uniform="roster-metric",
            )
        for index, card in enumerate(self.metric_cards):
            row, column = divmod(index, columns)
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 4, 0 if column == columns - 1 else 4),
                pady=(0 if row == 0 else 8, 0),
            )

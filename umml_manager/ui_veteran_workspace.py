from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .ui_veteran_lab import RosterLabPage
from .veteran_master_data import (
    VeteranMasterDataError,
    discover_master_mdb,
    resolve_veteran_records,
)
from .veterans import row_from_record


class VeteranRosterPage(RosterLabPage):
    """Final responsive roster workspace used by the standalone window.

    The workspace resolves game IDs against the user's current local
    ``master.mdb`` in read-only mode. Extracted snapshots and game files are
    never modified; unresolved or incompatible installations keep the raw
    extractor fields visible instead of receiving guessed labels.
    """

    def __init__(self, parent, app):
        self._workspace_after: str | None = None
        self._workspace_compact: bool | None = None
        self._master_data_note = ""
        super().__init__(parent, app)
        self._summary_panel = self.metrics.master
        self._compact_selected_actions()
        self.bind("<Configure>", self._queue_workspace_layout, add="+")
        self.bind("<Destroy>", self._cancel_pending_callbacks, add="+")
        self.after_idle(self._apply_workspace_layout)

    def load_snapshot(self, snapshot_id: str) -> None:
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            return
        try:
            raw_records = self.store.load_records(snapshot)
        except Exception as exc:
            messagebox.showerror(
                "Could not load veteran snapshot",
                str(exc),
                parent=self.app.root,
            )
            return

        master_path = discover_master_mdb(self.app)
        try:
            resolution = resolve_veteran_records(raw_records, master_path)
            self.records = resolution.records
            self._master_data_note = resolution.summary
        except VeteranMasterDataError as exc:
            # A stale, encrypted, or region-specific schema must not make the
            # roster unusable. Keep the validated scrubbed snapshot and explain
            # exactly why IDs could not be enriched.
            self.records = raw_records
            self._master_data_note = "Master-data resolution was skipped: " + str(exc)

        self.rows = [
            row_from_record(index, record)
            for index, record in enumerate(self.records)
        ]
        warning = " ".join(snapshot.warnings)
        self.notice_value.set(
            warning
            or (
                f"Imported from {snapshot.source_name}. Known account identifiers were removed "
                "before the immutable local snapshot was stored."
            )
        )
        self.apply_filter()

    def apply_filter(self) -> None:
        super().apply_filter()
        note = getattr(self, "_master_data_note", "").strip()
        if not note:
            return
        current = self.tool_hint_value.get().strip()
        self.tool_hint_value.set(f"{note}  {current}" if current else note)

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

    def _queue_workspace_layout(self, event) -> None:
        if event.widget is not self:
            return
        if self._workspace_after is not None:
            try:
                self.after_cancel(self._workspace_after)
            except tk.TclError:
                pass
        self._workspace_after = self.after(35, self._apply_workspace_layout)

    def _apply_workspace_layout(self) -> None:
        self._workspace_after = None
        try:
            scaling = float(self.tk.call("tk", "scaling"))
            height = self.winfo_height()
        except (tk.TclError, TypeError, ValueError):
            return

        # At increased text scaling, the metric summary is useful but not more
        # useful than the actual roster. Reclaim that fixed vertical space at a
        # compact height while preserving every search, filter, import, export,
        # and comparison control.
        compact = scaling >= 1.2 and height < 720
        if compact == self._workspace_compact:
            return
        self._workspace_compact = compact
        if compact:
            self._summary_panel.grid_remove()
        else:
            self._summary_panel.grid()

    def _cancel_pending_callbacks(self, event) -> None:
        if event.widget is not self:
            return
        for attribute in ("_workspace_after", "_layout_after", "_search_after"):
            callback = getattr(self, attribute, None)
            if callback is None:
                continue
            try:
                self.after_cancel(callback)
            except tk.TclError:
                pass
            setattr(self, attribute, None)

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

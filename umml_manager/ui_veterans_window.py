from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any

from .importer_safety import latest_regular_json
from .ui_veteran_external import (
    configure_external_extractor,
    launch_configured_extractor,
)
from .ui_veteran_presenter_v2 import VeteranRosterPage as _VeteranRosterPage
from .ui_veteran_providers import launch_provider_window
from .ui_windows import present_toplevel
from .veteran_analysis import evaluation_rank_from_record, evaluation_score
from .veteran_export import atomic_export_json
from .veterans import VeteranDataError, row_from_record


class VeteranRosterPage(_VeteranRosterPage):
    """Final window-facing roster page with hardened exports and teardown."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.bind("<Destroy>", self._cancel_pending_ui_callbacks, add="+")

    def _cancel_pending_ui_callbacks(self, event) -> None:
        if event.widget is not self:
            return
        for attribute in ("_layout_after", "_search_after"):
            callback_id = getattr(self, attribute, None)
            if callback_id is None:
                continue
            try:
                self.after_cancel(callback_id)
            except tk.TclError:
                pass
            setattr(self, attribute, None)

    def _sort_visible_rows(self) -> None:
        if getattr(self, "_sort_key", "") != "rank":
            super()._sort_visible_rows()
            return

        known: list[tuple[int, Any]] = []
        unknown: list[Any] = []
        for row in self.visible_rows:
            score = evaluation_score(self.records[row.index])
            if score is None:
                unknown.append(row)
            else:
                known.append((score, row))
        known.sort(key=lambda item: item[0], reverse=self._sort_reverse)
        self.visible_rows[:] = [row for _score, row in known] + unknown

    def _render_rows(self) -> None:
        super()._render_rows()
        for row in getattr(self, "visible_rows", ()):
            item_id = f"record-{row.index}"
            if not self.tree.exists(item_id):
                continue
            values = list(self.tree.item(item_id, "values"))
            if not values:
                continue
            values[0] = evaluation_rank_from_record(self.records[row.index])
            self.tree.item(item_id, values=values)

    def _record_selected(self, _event=None) -> None:
        super()._record_selected(_event)
        index = getattr(self, "_selected_index", None)
        if index is None or index < 0 or index >= len(getattr(self, "records", ())):
            return
        record = self.records[index]
        row = row_from_record(index, record)
        rank = evaluation_rank_from_record(record)
        identity = [
            f"Card {row.card_id}" if row.card_id else "",
            f"Character {row.chara_id}" if row.chara_id else "",
            f"Veteran {row.trained_chara_id}" if row.trained_chara_id else "",
            f"Rank {rank}" if rank != "—" else "",
        ]
        self.selected_subtitle_value.set(" · ".join(item for item in identity if item))

    def import_latest_output(self) -> None:
        latest = latest_regular_json(self.store.inbox)
        if latest is None:
            messagebox.showinfo(
                "No extractor output found",
                "No regular non-symlink JSON file exists in the isolated "
                f"extractor inbox:\n{self.store.inbox}",
                parent=self.app.root,
            )
            return
        self._import_path(latest)

    def export_selected(self) -> None:
        if self._selected_index is None:
            return
        row = row_from_record(
            self._selected_index,
            self.records[self._selected_index],
        )
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title="Export selected veteran",
            initialfile=(
                f"veteran-{row.trained_chara_id or self._selected_index + 1}.json"
            ),
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("All files", "*")),
        )
        if not path:
            return
        snapshot = self._selected_snapshot()
        payload: dict[str, Any] = {
            "snapshot_id": snapshot.id if snapshot is not None else "",
            "source_name": snapshot.source_name if snapshot is not None else "",
            "record": self.records[self._selected_index],
        }
        try:
            target = atomic_export_json(path, payload)
        except (OSError, VeteranDataError) as exc:
            messagebox.showerror(
                "Could not export veteran",
                str(exc),
                parent=self.winfo_toplevel(),
            )
            return
        self.app.status.set(f"Exported selected veteran to {target}")


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

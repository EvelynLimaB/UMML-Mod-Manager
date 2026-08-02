from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

from .ui_veteran_workspace import VeteranRosterPage as _WorkspaceVeteranRosterPage
from .veteran_media import VeteranMediaResult


class VeteranRosterPage(_WorkspaceVeteranRosterPage):
    """Presentation layer for the full-size roster window.

    The data-aware workspace keeps its dedicated Media tab, while this layer
    makes the selected costume artwork part of the primary browsing experience.
    Only one stable selection is fetched at a time, after a short debounce, and
    the validated Manager-owned cache remains the source used by Tk.
    """

    def __init__(self, parent, app):
        self._portrait_after: str | None = None
        self._portrait_request: tuple[str, tuple[int, ...]] | None = None
        self._portrait_failures: set[str] = set()
        self._detail_portrait_photo: ImageTk.PhotoImage | None = None
        self._roster_portrait_photos: dict[int, ImageTk.PhotoImage] = {}
        super().__init__(parent, app)
        self._build_primary_portrait()
        self.after_idle(self._queue_primary_portrait)

    def _build_primary_portrait(self) -> None:
        right = self.detail_notebook.master
        right.columnconfigure(0, weight=0)
        right.columnconfigure(1, weight=1)
        right.rowconfigure(3, weight=1)

        title = _widget_for_textvariable(right, self.selected_title_value)
        subtitle = _widget_for_textvariable(right, self.selected_subtitle_value)
        action_bar = self.pin_button.master
        if title is not None:
            title.grid_configure(row=0, column=1, sticky="ew", padx=(12, 0))
            title.configure(wraplength=650)
        if subtitle is not None:
            subtitle.grid_configure(row=1, column=1, sticky="ew", padx=(12, 0))
            subtitle.configure(wraplength=650)
        action_bar.grid_configure(row=2, column=1, sticky="ew", padx=(12, 0))
        self.detail_notebook.grid_configure(row=3, column=0, columnspan=2, sticky="nsew")

        self.primary_portrait_host = tk.Frame(
            right,
            background=self._colors["soft"],
            width=184,
            height=214,
            highlightthickness=1,
            highlightbackground=self._colors["border"],
        )
        self.primary_portrait_host.grid(
            row=0,
            column=0,
            rowspan=3,
            sticky="nw",
            pady=(0, 10),
        )
        self.primary_portrait_host.grid_propagate(False)
        self.primary_portrait_host.rowconfigure(0, weight=1)
        self.primary_portrait_host.columnconfigure(0, weight=1)

        self.primary_portrait_label = tk.Label(
            self.primary_portrait_host,
            text="Select a veteran\nto show costume art",
            background=self._colors["soft"],
            foreground=self._colors["muted"],
            justify="center",
            wraplength=150,
            borderwidth=0,
        )
        self.primary_portrait_label.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.primary_portrait_button = ttk.Button(
            self.primary_portrait_host,
            text="Load portrait",
            style="Roster.TButton",
            command=self.load_primary_portrait,
        )
        self.primary_portrait_button.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        # Treeview supports an image in its first column. Rows receive a small
        # cached thumbnail as they are visited, while the selected record gets a
        # large readable portrait in the detail header.
        ttk.Style(self).configure("Roster.Treeview", rowheight=42)
        self._apply_primary_portrait_layout()

    def _record_selected(self, _event=None) -> None:
        super()._record_selected(_event)
        if hasattr(self, "primary_portrait_label"):
            self._queue_primary_portrait()

    def _render_rows(self) -> None:
        super()._render_rows()
        for index, photo in self._roster_portrait_photos.items():
            item_id = f"record-{index}"
            if self.tree.exists(item_id):
                self.tree.item(item_id, image=photo)

    def _render_media(self, result: VeteranMediaResult) -> None:
        super()._render_media(result)
        if hasattr(self, "primary_portrait_label"):
            self._render_primary_portrait(result.portrait)

    def _queue_primary_portrait(self) -> None:
        if self._portrait_after is not None:
            try:
                self.after_cancel(self._portrait_after)
            except tk.TclError:
                pass
        self._portrait_after = self.after(280, self._refresh_primary_portrait)

    def _refresh_primary_portrait(self) -> None:
        self._portrait_after = None
        selection = self._selected_media_ids()
        if selection is None:
            self._detail_portrait_photo = None
            self.primary_portrait_label.configure(
                image="",
                text="Select a veteran\nto show costume art",
            )
            self.primary_portrait_button.configure(state="disabled", text="Load portrait")
            return

        card_id, _skill_ids = selection
        self.primary_portrait_button.configure(state="normal", text="Reload portrait")
        try:
            cached = self._get_media_cache().cached_selection(card_id, ())
        except Exception as exc:
            self.primary_portrait_label.configure(
                image="",
                text=f"Portrait cache unavailable\n{exc}",
            )
            return
        if cached.portrait is not None:
            self._render_primary_portrait(cached.portrait)
            return

        self._detail_portrait_photo = None
        self.primary_portrait_label.configure(image="", text="Loading costume art…")
        self.primary_portrait_button.configure(state="disabled", text="Loading…")
        if card_id not in self._portrait_failures:
            self._request_primary_portrait(selection)
        else:
            self.primary_portrait_label.configure(
                image="",
                text="Portrait unavailable\nUse Retry portrait",
            )
            self.primary_portrait_button.configure(state="normal", text="Retry portrait")

    def load_primary_portrait(self) -> None:
        selection = self._selected_media_ids()
        if selection is None:
            return
        self._portrait_failures.discard(selection[0])
        self._request_primary_portrait(selection, force=True)

    def _request_primary_portrait(
        self,
        selection: tuple[str, tuple[int, ...]],
        *,
        force: bool = False,
    ) -> None:
        if self._portrait_request is not None:
            if not force or self._portrait_request == selection:
                return
        card_id, _skill_ids = selection
        cache = self._get_media_cache()
        self._portrait_request = selection
        self.primary_portrait_button.configure(state="disabled", text="Loading…")

        def completed(result: VeteranMediaResult) -> None:
            self._portrait_request = None
            current = self._selected_media_ids()
            if current != selection:
                self._queue_primary_portrait()
                return
            if result.portrait is None:
                self._portrait_failures.add(card_id)
                self.primary_portrait_label.configure(
                    image="",
                    text="Portrait unavailable\nUse Retry portrait",
                )
                self.primary_portrait_button.configure(state="normal", text="Retry portrait")
                return
            self._portrait_failures.discard(card_id)
            # Re-render the whole selected media state so the existing Media tab
            # and the primary portrait remain synchronized.
            self._render_media(cache.cached_selection(*selection))
            self.primary_portrait_button.configure(state="normal", text="Reload portrait")

        def failed(exc: Exception) -> None:
            self._portrait_request = None
            self._portrait_failures.add(card_id)
            if self._selected_media_ids() != selection:
                self._queue_primary_portrait()
                return
            self.primary_portrait_label.configure(
                image="",
                text=f"Portrait unavailable\n{exc}",
            )
            self.primary_portrait_button.configure(state="normal", text="Retry portrait")

        runner = getattr(self.app, "_run_task", None)
        if not callable(runner):
            failed(RuntimeError("background task runner is unavailable"))
            return
        runner(
            "Loading selected veteran portrait…",
            lambda: cache.fetch_selection(card_id, ()),
            completed,
            failed=failed,
        )

    def _render_primary_portrait(self, path: Path | None) -> None:
        if not hasattr(self, "primary_portrait_label"):
            return
        if path is None:
            self._detail_portrait_photo = None
            self.primary_portrait_label.configure(
                image="",
                text="No costume artwork cached",
            )
            return

        detail_photo = _photo(path, (174, 174))
        if detail_photo is None:
            self._detail_portrait_photo = None
            self.primary_portrait_label.configure(
                image="",
                text="Cached portrait could not be decoded",
            )
            return
        self._detail_portrait_photo = detail_photo
        self.primary_portrait_label.configure(image=detail_photo, text="")

        index = getattr(self, "_selected_index", None)
        if index is None:
            return
        thumbnail = _photo(path, (34, 34))
        if thumbnail is None:
            return
        self._roster_portrait_photos[index] = thumbnail
        item_id = f"record-{index}"
        if self.tree.exists(item_id):
            self.tree.item(item_id, image=thumbnail)

    def _apply_workspace_layout(self) -> None:
        super()._apply_workspace_layout()
        if hasattr(self, "primary_portrait_host"):
            self._apply_primary_portrait_layout()

    def _apply_primary_portrait_layout(self) -> None:
        try:
            width = self.winfo_width()
            height = self.winfo_height()
        except tk.TclError:
            return
        compact = width < 1220 or height < 720
        if compact:
            self.primary_portrait_host.configure(width=148, height=188)
            self.primary_portrait_label.configure(wraplength=120)
        else:
            self.primary_portrait_host.configure(width=184, height=214)
            self.primary_portrait_label.configure(wraplength=150)

    def _cancel_pending_callbacks(self, event) -> None:
        if event.widget is self and self._portrait_after is not None:
            try:
                self.after_cancel(self._portrait_after)
            except tk.TclError:
                pass
            self._portrait_after = None
        super()._cancel_pending_callbacks(event)


def _widget_for_textvariable(parent: tk.Misc, variable: tk.Variable):
    expected = str(variable)
    for child in parent.winfo_children():
        try:
            if str(child.cget("textvariable")) == expected:
                return child
        except (AttributeError, TypeError, tk.TclError):
            continue
    return None


def _photo(path: Path, size: tuple[int, int]) -> ImageTk.PhotoImage | None:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.thumbnail(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
    except (OSError, ValueError, tk.TclError):
        return None

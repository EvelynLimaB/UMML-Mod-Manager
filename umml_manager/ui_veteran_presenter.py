from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

from .ui_veteran_workspace import VeteranRosterPage as _WorkspaceVeteranRosterPage
from .veteran_local_portraits import LocalPortraitCache
from .veteran_media import VeteranMediaResult
from .veterans import row_from_record


class VeteranRosterPage(_WorkspaceVeteranRosterPage):
    """Presentation layer for the full-size roster window.

    The roster is a working surface, not a stack of permanent setup forms. A
    compact command strip keeps search and sort available while setup, advanced
    filters, and summary metrics can be revealed independently. Costume art is
    read from the installed game first and falls back to the validated remote
    cache only when the local asset cannot be resolved.
    """

    def __init__(self, parent, app):
        self._portrait_after: str | None = None
        self._portrait_request: tuple[str, tuple[int, ...]] | None = None
        self._portrait_failures: set[str] = set()
        self._detail_portrait_photo: ImageTk.PhotoImage | None = None
        self._roster_portrait_photos: dict[int, ImageTk.PhotoImage] = {}
        self._local_portrait_cache: LocalPortraitCache | None = None
        self._top_panels: dict[str, tk.Misc] = {}
        self._top_section_visible = {
            "setup": False,
            "advanced": False,
            "summary": False,
        }
        self._focus_mode = False
        self._focus_saved_sections: dict[str, bool] | None = None
        self._preload_running = False
        super().__init__(parent, app)
        self._build_primary_portrait()
        self._build_workspace_chrome()
        self.after_idle(self._prime_cached_thumbnails)
        self.after_idle(self._queue_primary_portrait)

    def apply_filter(self) -> None:
        super().apply_filter()
        if hasattr(self, "chrome_status_value"):
            self._update_chrome_status()

    def _build_workspace_chrome(self) -> None:
        setup = _row_widget(self, 0)
        advanced = _row_widget(self, 1)
        summary = _row_widget(self, 2)
        main = _row_widget(self, 3)
        if None in (setup, advanced, summary, main):
            return

        self._top_panels = {
            "setup": setup,
            "advanced": advanced,
            "summary": summary,
        }
        setup.grid_configure(row=1)
        advanced.grid_configure(row=2)
        summary.grid_configure(row=3)
        main.grid_configure(row=4)
        for row in range(4):
            self.rowconfigure(row, weight=0)
        self.rowconfigure(4, weight=1)

        chrome = ttk.Frame(
            self,
            style="Roster.Surface.TFrame",
            padding=(12, 8),
        )
        chrome.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        chrome.columnconfigure(2, weight=1)
        chrome.columnconfigure(7, weight=1)

        ttk.Label(
            chrome,
            text="Roster",
            style="RosterSectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(
            chrome,
            text="Search",
            style="RosterEyebrow.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(0, 6))
        self.quick_search_entry = ttk.Entry(
            chrome,
            textvariable=self.search_value,
            style="Roster.TEntry",
        )
        self.quick_search_entry.grid(row=0, column=2, sticky="ew", padx=(0, 10))
        self.quick_search_entry.bind("<KeyRelease>", lambda _event: self.apply_filter())

        ttk.Label(
            chrome,
            text="Sort",
            style="RosterEyebrow.TLabel",
        ).grid(row=0, column=3, sticky="w", padx=(0, 6))
        self.quick_sort_box = ttk.Combobox(
            chrome,
            textvariable=self.sort_value,
            values=self.sort_box.cget("values"),
            state="readonly",
            width=18,
            style="Roster.TCombobox",
        )
        self.quick_sort_box.grid(row=0, column=4, sticky="ew", padx=(0, 8))
        self.quick_sort_box.bind("<<ComboboxSelected>>", self._sort_selected)
        ttk.Button(
            chrome,
            text="Clear",
            style="Roster.TButton",
            command=self.clear_filters,
        ).grid(row=0, column=5, sticky="ew", padx=(0, 8))
        self.focus_button = ttk.Button(
            chrome,
            text="Focus mode",
            style="RosterAccent.TButton",
            command=self.toggle_focus_mode,
        )
        self.focus_button.grid(row=0, column=6, sticky="ew")

        controls = ttk.Frame(chrome, style="Roster.Surface.TFrame")
        controls.grid(row=1, column=0, columnspan=7, sticky="w", pady=(7, 0))
        self.setup_toggle_button = ttk.Button(
            controls,
            style="Roster.TButton",
            command=lambda: self.toggle_top_section("setup"),
        )
        self.setup_toggle_button.pack(side="left")
        self.advanced_toggle_button = ttk.Button(
            controls,
            style="Roster.TButton",
            command=lambda: self.toggle_top_section("advanced"),
        )
        self.advanced_toggle_button.pack(side="left", padx=(6, 0))
        self.summary_toggle_button = ttk.Button(
            controls,
            style="Roster.TButton",
            command=lambda: self.toggle_top_section("summary"),
        )
        self.summary_toggle_button.pack(side="left", padx=(6, 0))
        self.preload_portraits_button = ttk.Button(
            controls,
            text="Preload all portraits",
            style="Roster.TButton",
            command=self.preload_all_portraits,
        )
        self.preload_portraits_button.pack(side="left", padx=(12, 0))

        self.chrome_status_value = tk.StringVar(master=chrome, value="")
        ttk.Label(
            chrome,
            textvariable=self.chrome_status_value,
            style="RosterSurfaceMuted.TLabel",
            justify="right",
            anchor="e",
        ).grid(row=1, column=7, sticky="e", padx=(12, 0), pady=(7, 0))

        top = self.winfo_toplevel()
        top.bind("<F6>", lambda _event: self.toggle_top_section("setup"), add="+")
        top.bind("<F7>", lambda _event: self.toggle_top_section("advanced"), add="+")
        top.bind("<F8>", lambda _event: self.toggle_top_section("summary"), add="+")
        top.bind("<F9>", lambda _event: self.toggle_focus_mode(), add="+")

        self._apply_top_section_visibility()
        self._update_chrome_status()

    def toggle_top_section(self, section: str) -> None:
        if section not in self._top_section_visible:
            return
        if self._focus_mode:
            self._focus_mode = False
            self._focus_saved_sections = None
        self._top_section_visible[section] = not self._top_section_visible[section]
        self._apply_top_section_visibility()

    def toggle_focus_mode(self) -> None:
        if self._focus_mode:
            self._focus_mode = False
            if self._focus_saved_sections is not None:
                self._top_section_visible.update(self._focus_saved_sections)
            self._focus_saved_sections = None
        else:
            self._focus_saved_sections = dict(self._top_section_visible)
            self._focus_mode = True
        self._apply_top_section_visibility()

    def _apply_top_section_visibility(self) -> None:
        if not self._top_panels:
            return
        for name, panel in self._top_panels.items():
            visible = self._top_section_visible.get(name, False) and not self._focus_mode
            if visible:
                panel.grid()
            else:
                panel.grid_remove()

        labels = {
            "setup": "Setup & export",
            "advanced": "Advanced filters",
            "summary": "Summary",
        }
        buttons = {
            "setup": getattr(self, "setup_toggle_button", None),
            "advanced": getattr(self, "advanced_toggle_button", None),
            "summary": getattr(self, "summary_toggle_button", None),
        }
        for name, button in buttons.items():
            if button is None:
                continue
            marker = "▾" if self._top_section_visible[name] and not self._focus_mode else "▸"
            button.configure(text=f"{marker} {labels[name]}")
        if hasattr(self, "focus_button"):
            self.focus_button.configure(
                text="Exit focus" if self._focus_mode else "Focus mode"
            )

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
        self.detail_notebook.grid_configure(
            row=3,
            column=1,
            columnspan=1,
            sticky="nsew",
            padx=(12, 0),
        )

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
            rowspan=4,
            sticky="n",
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
        if hasattr(self, "chrome_status_value"):
            self._update_chrome_status()

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
        cached = self._cached_portrait(card_id)
        if cached is not None:
            self._render_primary_portrait(cached)
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
        self._portrait_request = selection
        self.primary_portrait_button.configure(state="disabled", text="Loading…")

        def work() -> VeteranMediaResult:
            local = self._get_local_portrait_cache().extract(card_id)
            if local.portrait is not None:
                return VeteranMediaResult(
                    portrait=local.portrait,
                    skill_icons=(),
                    cache_hits=int(local.cache_hit),
                    downloads=0,
                    warnings=(("Loaded from installed game assets."),),
                )
            remote = self._get_media_cache().fetch_selection(card_id, ())
            if local.warning and remote.portrait is None:
                return VeteranMediaResult(
                    portrait=None,
                    skill_icons=(),
                    cache_hits=remote.cache_hits,
                    downloads=remote.downloads,
                    warnings=(local.warning, *remote.warnings),
                )
            return remote

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
            self._render_media(result)
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
            work,
            completed,
            failed=failed,
        )

    def preload_all_portraits(self) -> None:
        if self._preload_running:
            return
        card_ids = self._unique_card_ids()
        if not card_ids:
            self.chrome_status_value.set("No card IDs are available to preload.")
            return

        self._preload_running = True
        self.preload_portraits_button.configure(state="disabled", text="Preloading…")
        self.chrome_status_value.set(
            f"Preloading {len(card_ids):,} unique portrait(s), local assets first…"
        )

        def work() -> dict[str, object]:
            local_cache = self._get_local_portrait_cache()
            remote_cache = self._get_media_cache()
            cached = 0
            local_count = 0
            remote_count = 0
            warnings: list[str] = []
            for card_id in card_ids:
                if self._cached_portrait(card_id) is not None:
                    cached += 1
                    continue
                local = local_cache.extract(card_id)
                if local.portrait is not None:
                    local_count += 1
                    continue
                remote = remote_cache.fetch_selection(card_id, ())
                if remote.portrait is not None:
                    remote_count += 1
                else:
                    warning = " ".join((local.warning, *remote.warnings)).strip()
                    if warning:
                        warnings.append(f"{card_id}: {warning}")
            return {
                "total": len(card_ids),
                "cached": cached,
                "local": local_count,
                "remote": remote_count,
                "warnings": tuple(warnings),
            }

        def completed(result: dict[str, object]) -> None:
            self._preload_running = False
            self.preload_portraits_button.configure(
                state="normal",
                text="Preload all portraits",
            )
            self._prime_cached_thumbnails()
            loaded = int(result["cached"]) + int(result["local"]) + int(result["remote"])
            status = (
                f"Portrait cache {loaded:,}/{int(result['total']):,}: "
                f"{int(result['local']):,} local, {int(result['remote']):,} remote, "
                f"{int(result['cached']):,} already cached."
            )
            warnings = result.get("warnings") or ()
            if warnings:
                status += f" {len(warnings):,} unavailable."
            self.chrome_status_value.set(status)

        def failed(exc: Exception) -> None:
            self._preload_running = False
            self.preload_portraits_button.configure(
                state="normal",
                text="Preload all portraits",
            )
            self.chrome_status_value.set(f"Portrait preload stopped: {exc}")

        self.app._run_task(
            "Preloading unique veteran portraits…",
            work,
            completed,
            failed=failed,
        )

    def _unique_card_ids(self) -> tuple[str, ...]:
        card_ids: set[str] = set()
        for index, record in enumerate(getattr(self, "records", ())):
            card_id = row_from_record(index, record).card_id
            if card_id:
                card_ids.add(str(card_id))
        return tuple(sorted(card_ids, key=lambda value: int(value) if value.isdigit() else value))

    def _prime_cached_thumbnails(self) -> None:
        card_photos: dict[str, ImageTk.PhotoImage] = {}
        row_photos: dict[int, ImageTk.PhotoImage] = {}
        for index, record in enumerate(getattr(self, "records", ())):
            card_id = row_from_record(index, record).card_id
            if not card_id:
                continue
            key = str(card_id)
            photo = card_photos.get(key)
            if photo is None:
                path = self._cached_portrait(key)
                if path is None:
                    continue
                photo = _photo(path, (34, 34))
                if photo is None:
                    continue
                card_photos[key] = photo
            row_photos[index] = photo
        self._roster_portrait_photos = row_photos
        for index, photo in row_photos.items():
            item_id = f"record-{index}"
            if self.tree.exists(item_id):
                self.tree.item(item_id, image=photo)
        self._update_chrome_status()

    def _cached_portrait(self, card_id: object) -> Path | None:
        local = self._get_local_portrait_cache().cached(card_id)
        if local is not None:
            return local
        return self._get_media_cache().cached_selection(card_id, ()).portrait

    def _get_local_portrait_cache(self) -> LocalPortraitCache:
        if self._local_portrait_cache is None:
            self._local_portrait_cache = LocalPortraitCache.from_app(
                self.app,
                Path(self.store.root) / "media-cache",
            )
        return self._local_portrait_cache

    def _update_chrome_status(self) -> None:
        if not hasattr(self, "chrome_status_value"):
            return
        card_ids = self._unique_card_ids()
        cached = sum(self._cached_portrait(card_id) is not None for card_id in card_ids)
        visible = len(getattr(self, "filtered_rows", ()))
        total = len(getattr(self, "rows", ()))
        self.chrome_status_value.set(
            f"{visible:,}/{total:,} veterans · {cached:,}/{len(card_ids):,} portraits cached"
        )

    def clear_media_cache(self) -> None:
        super().clear_media_cache()
        self._detail_portrait_photo = None
        self._roster_portrait_photos.clear()
        self._portrait_failures.clear()
        self._queue_primary_portrait()
        self._update_chrome_status()

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
        if self._top_panels:
            self._apply_top_section_visibility()

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


def _row_widget(parent: tk.Misc, row: int):
    widgets = parent.grid_slaves(row=row)
    return widgets[0] if widgets else None


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

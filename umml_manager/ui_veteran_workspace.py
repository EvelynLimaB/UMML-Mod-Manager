from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from PIL import Image, ImageTk

from .ui_veteran_lab import RosterLabPage
from .veteran_master_data import (
    VeteranMasterDataError,
    discover_master_mdb,
    resolve_veteran_records,
)
from .veteran_media import VeteranMediaCache, VeteranMediaError, VeteranMediaResult
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
        self._media_cache: VeteranMediaCache | None = None
        self._media_photos: list[ImageTk.PhotoImage] = []
        self._media_selection: tuple[str, tuple[int, ...]] | None = None
        super().__init__(parent, app)
        self._summary_panel = self.metrics.master
        self._build_media_tab()
        self._compact_selected_actions()
        self.bind("<Configure>", self._queue_workspace_layout, add="+")
        self.bind("<Destroy>", self._cancel_pending_callbacks, add="+")
        self.after_idle(self._apply_workspace_layout)
        self._show_cached_media()

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

    def _record_selected(self, _event=None) -> None:
        super()._record_selected(_event)
        if hasattr(self, "media_status_value"):
            self._show_cached_media()

    def _build_media_tab(self) -> None:
        self.media_tab = ttk.Frame(
            self.detail_notebook,
            style="Roster.Soft.TFrame",
            padding=(12, 12),
        )
        self.detail_notebook.add(self.media_tab, text="Media")
        self.media_tab.columnconfigure(1, weight=1)
        self.media_tab.rowconfigure(1, weight=1)

        self.media_status_value = tk.StringVar(
            master=self.media_tab,
            value=(
                "Artwork is optional and never bundled. Load it explicitly to cache the "
                "selected costume and up to 12 skill icons from approved HTTPS hosts."
            ),
        )
        ttk.Label(
            self.media_tab,
            textvariable=self.media_status_value,
            style="RosterSoft.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.portrait_host = tk.Frame(
            self.media_tab,
            background=self._colors["soft"],
            width=220,
            height=220,
        )
        self.portrait_host.grid(row=1, column=0, sticky="nw", padx=(0, 12))
        self.portrait_host.grid_propagate(False)
        self.portrait_label = tk.Label(
            self.portrait_host,
            text="No artwork cached",
            background=self._colors["soft"],
            foreground=self._colors["muted"],
            justify="center",
            wraplength=190,
        )
        self.portrait_label.place(relx=0.5, rely=0.5, anchor="center")

        skills_panel = ttk.Frame(self.media_tab, style="Roster.Soft.TFrame")
        skills_panel.grid(row=1, column=1, sticky="nsew")
        skills_panel.columnconfigure(0, weight=1)
        ttk.Label(
            skills_panel,
            text="Selected skill icons",
            style="RosterSoftSection.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.skill_icon_host = tk.Frame(
            skills_panel,
            background=self._colors["soft"],
        )
        self.skill_icon_host.grid(row=1, column=0, sticky="nsew")

        actions = ttk.Frame(self.media_tab, style="Roster.Soft.TFrame")
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.load_media_button = ttk.Button(
            actions,
            text="Load selected artwork",
            style="RosterAccent.TButton",
            command=self.load_selected_media,
        )
        self.load_media_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.clear_media_button = ttk.Button(
            actions,
            text="Clear artwork cache",
            style="Roster.TButton",
            command=self.clear_media_cache,
        )
        self.clear_media_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        ttk.Label(
            self.media_tab,
            text=(
                "Images are served by GameTora and retained only in the Manager-owned local "
                "cache. Names, IDs, stars, and descriptions come from your master.mdb."
            ),
            style="RosterSurfaceMuted.TLabel",
            wraplength=430,
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(9, 0))

    def load_selected_media(self) -> None:
        selection = self._selected_media_ids()
        if selection is None:
            self.media_status_value.set("Select a veteran before loading artwork.")
            return
        card_id, skill_ids = selection
        cache = self._get_media_cache()
        self.media_status_value.set("Downloading and validating optional roster artwork…")
        self.load_media_button.configure(state="disabled")

        def completed(result: VeteranMediaResult) -> None:
            self.load_media_button.configure(state="normal")
            current = self._selected_media_ids()
            if current != selection:
                return
            self._render_media(result)

        def failed(exc: Exception) -> None:
            self.load_media_button.configure(state="normal")
            self.media_status_value.set(f"Artwork could not be loaded: {exc}")

        self.app._run_task(
            "Loading optional roster artwork…",
            lambda: cache.fetch_selection(card_id, skill_ids),
            completed,
            failed=failed,
        )

    def clear_media_cache(self) -> None:
        try:
            removed = self._get_media_cache().clear()
        except Exception as exc:
            self.media_status_value.set(f"Artwork cache could not be cleared: {exc}")
            return
        self._media_selection = None
        self._clear_media_widgets()
        self.media_status_value.set(f"Cleared {removed:,} cached image(s).")

    def _show_cached_media(self) -> None:
        selection = self._selected_media_ids()
        if selection is None:
            if hasattr(self, "media_status_value"):
                self.media_status_value.set("Select a veteran to inspect optional artwork.")
                self._clear_media_widgets()
            return
        if selection == self._media_selection:
            return
        try:
            result = self._get_media_cache().cached_selection(*selection)
        except Exception as exc:
            self.media_status_value.set(f"Artwork cache is unavailable: {exc}")
            return
        self._render_media(result)

    def _render_media(self, result: VeteranMediaResult) -> None:
        self._clear_media_widgets()
        selection = self._selected_media_ids()
        self._media_selection = selection
        loaded = 0

        if result.portrait is not None:
            photo = self._photo(result.portrait, (210, 210))
            if photo is not None:
                self._media_photos.append(photo)
                self.portrait_label.configure(image=photo, text="")
                loaded += 1
        if loaded == 0:
            self.portrait_label.configure(image="", text="No costume artwork cached")

        names = self._selected_skill_names()
        for position, (skill_id, path) in enumerate(result.skill_icons):
            photo = self._photo(path, (48, 48))
            if photo is None:
                continue
            self._media_photos.append(photo)
            card = tk.Frame(
                self.skill_icon_host,
                background=self._colors["soft"],
                padx=3,
                pady=3,
            )
            row, column = divmod(position, 4)
            card.grid(row=row, column=column, sticky="n", padx=3, pady=3)
            tk.Label(
                card,
                image=photo,
                background=self._colors["soft"],
                borderwidth=0,
            ).pack()
            tk.Label(
                card,
                text=names.get(skill_id, str(skill_id)),
                background=self._colors["soft"],
                foreground=self._colors["text"],
                wraplength=82,
                justify="center",
                font=("TkDefaultFont", 8),
            ).pack(pady=(2, 0))
            loaded += 1

        if result.portrait is None and not result.skill_icons:
            self.media_status_value.set(
                "No artwork is cached for this selection. Use Load selected artwork to fetch it."
            )
            return
        status = (
            f"Showing {loaded:,} validated cached image(s): "
            f"{result.cache_hits:,} cache hit(s), {result.downloads:,} new download(s)."
        )
        if result.warnings:
            status += " " + " ".join(result.warnings[:3])
        self.media_status_value.set(status)

    def _clear_media_widgets(self) -> None:
        if not hasattr(self, "portrait_label"):
            return
        self._media_photos.clear()
        self.portrait_label.configure(image="", text="No artwork cached")
        for child in self.skill_icon_host.winfo_children():
            child.destroy()

    def _selected_media_ids(self) -> tuple[str, tuple[int, ...]] | None:
        index = getattr(self, "_selected_index", None)
        if index is None or index < 0 or index >= len(getattr(self, "records", ())):
            return None
        record = self.records[index]
        row = row_from_record(index, record)
        if not row.card_id:
            return None
        skill_ids: list[int] = []
        raw_skills = record.get("skill_array")
        if isinstance(raw_skills, (list, tuple)):
            for item in raw_skills:
                value: Any = item
                if isinstance(item, dict):
                    value = item.get("skill_id", item.get("skillId", item.get("id")))
                try:
                    skill_id = int(value)
                except (TypeError, ValueError):
                    continue
                if skill_id > 0:
                    skill_ids.append(skill_id)
        return row.card_id, tuple(skill_ids)

    def _selected_skill_names(self) -> dict[int, str]:
        index = getattr(self, "_selected_index", None)
        if index is None or index < 0 or index >= len(getattr(self, "records", ())):
            return {}
        result: dict[int, str] = {}
        raw_skills = self.records[index].get("skill_array")
        if not isinstance(raw_skills, (list, tuple)):
            return result
        for item in raw_skills:
            if not isinstance(item, dict):
                continue
            try:
                skill_id = int(item.get("skill_id", item.get("skillId", item.get("id"))))
            except (TypeError, ValueError):
                continue
            name = str(
                item.get("skill_name")
                or item.get("skillName")
                or item.get("name")
                or skill_id
            )
            result[skill_id] = name
        return result

    def _get_media_cache(self) -> VeteranMediaCache:
        if self._media_cache is None:
            self._media_cache = VeteranMediaCache(
                Path(self.store.root) / "media-cache"
            )
        return self._media_cache

    @staticmethod
    def _photo(path: Path, size: tuple[int, int]) -> ImageTk.PhotoImage | None:
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
                image.thumbnail(size, Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image)
        except (OSError, ValueError, tk.TclError):
            return None

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

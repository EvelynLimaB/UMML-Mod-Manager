from __future__ import annotations

import queue
import tkinter as tk
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageColor, ImageDraw, ImageTk

from .ui_veteran_presenter import VeteranRosterPage as _PreviousVeteranRosterPage
from .ui_veteran_workspace import VeteranRosterPage as _WorkspaceVeteranRosterPage
from .veteran_media import VeteranMediaCache, VeteranMediaResult
from .veteran_portrait_loader import PortraitLoadResult, VeteranPortraitResolver
from .veterans import row_from_record


class VeteranRosterPage(_PreviousVeteranRosterPage):
    """Roster workspace with correct grid ownership and incremental artwork loading.

    The previous pass accidentally placed the inherited credit footer and the
    main paned workspace on the same grid row. It also queued portrait work as a
    single sequential batch, so nothing appeared until the whole batch ended.
    This layer gives every structural region one row, prioritizes the selected
    and currently visible records, and renders each completed portrait at once.
    """

    def __init__(self, parent, app):
        self._portrait_events: queue.SimpleQueue[tuple] = queue.SimpleQueue()
        self._portrait_event_after: str | None = None
        self._auto_preload_after: str | None = None
        self._visible_preload_after: str | None = None
        self._priority_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="umml-roster-priority",
        )
        self._background_executor = ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="umml-roster-background",
        )
        self._portrait_futures: dict[str, Future] = {}
        self._skill_future: Future | None = None
        self._skill_generation = 0
        self._card_rows: dict[str, tuple[int, ...]] = {}
        self._card_photos: dict[str, ImageTk.PhotoImage] = {}
        self._failed_cards: set[str] = set()
        self._placeholders: dict[str, ImageTk.PhotoImage] = {}
        self._resolver: VeteranPortraitResolver | None = None
        self._credits_footer: tk.Misc | None = None
        self._main_workspace: tk.Misc | None = None
        self._portrait_progress_host: ttk.Frame | None = None
        self._portrait_progress_value: tk.DoubleVar | None = None
        self._portrait_progress_label_value: tk.StringVar | None = None
        self._destroying = False

        super().__init__(parent, app)

        self._resolver = VeteranPortraitResolver(
            self._get_local_portrait_cache(),
            self._get_media_cache(),
        )
        self._repair_workspace_grid()
        self._build_loading_feedback()
        self._build_placeholders()
        self._reindex_card_rows()
        self._restore_row_art()

        self.tree.bind("<MouseWheel>", self._queue_visible_portraits, add="+")
        self.tree.bind("<Button-4>", self._queue_visible_portraits, add="+")
        self.tree.bind("<Button-5>", self._queue_visible_portraits, add="+")
        self.tree.bind("<Configure>", self._queue_visible_portraits, add="+")
        self.tree.bind("<KeyRelease>", self._queue_visible_portraits, add="+")
        self.bind("<Destroy>", self._shutdown_portrait_workers, add="+")

        self._auto_preload_after = self.after(450, self._auto_preload_portraits)
        self.after_idle(self.configure_workspace_rows)

    # ------------------------------------------------------------------
    # Workspace structure

    def _repair_workspace_grid(self) -> None:
        main = _direct_child(self, self.tree)
        footer = None
        for child in self.winfo_children():
            if child is main or child in self._top_panels.values():
                continue
            try:
                row = int(child.grid_info().get("row", -1))
            except (TypeError, ValueError, tk.TclError):
                continue
            if row == 4:
                footer = child
                break

        self._main_workspace = main
        self._credits_footer = footer
        if main is not None:
            main.grid_configure(row=4)
        if footer is not None:
            footer.grid_configure(row=5)
            footer.grid_remove()
        self.configure_workspace_rows()

    def configure_workspace_rows(self) -> None:
        """Keep only the actual list/detail workspace vertically expandable."""

        for row in range(6):
            self.rowconfigure(row, weight=0)
        self.rowconfigure(4, weight=1)

    def _apply_top_section_visibility(self) -> None:
        super()._apply_top_section_visibility()
        footer = getattr(self, "_credits_footer", None)
        if footer is None:
            return
        show_credits = (
            self._top_section_visible.get("setup", False)
            and not self._focus_mode
        )
        if show_credits:
            footer.grid()
        else:
            footer.grid_remove()
        self.configure_workspace_rows()

    # ------------------------------------------------------------------
    # Compact loading feedback

    def _build_loading_feedback(self) -> None:
        chrome = self.quick_search_entry.master
        chrome.columnconfigure(7, weight=1)
        self.preload_portraits_button.configure(text="Refresh portraits")

        host = ttk.Frame(chrome, style="Roster.Surface.TFrame")
        host.grid(row=2, column=0, columnspan=8, sticky="ew", pady=(7, 0))
        host.columnconfigure(0, weight=1)
        self._portrait_progress_host = host
        self._portrait_progress_value = tk.DoubleVar(master=host, value=0)
        self._portrait_progress_label_value = tk.StringVar(master=host, value="")
        ttk.Progressbar(
            host,
            variable=self._portrait_progress_value,
            maximum=1,
            mode="determinate",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Label(
            host,
            textvariable=self._portrait_progress_label_value,
            style="RosterSurfaceMuted.TLabel",
        ).grid(row=0, column=1, sticky="e")
        host.grid_remove()

    def _build_placeholders(self) -> None:
        background = ImageColor.getrgb(self._colors["soft"])
        border = ImageColor.getrgb(self._colors["border"])
        muted = ImageColor.getrgb(self._colors["muted"])
        accent = ImageColor.getrgb(self._colors["accent"])
        self._placeholders = {
            "empty": _placeholder_photo(background, border, muted, "·"),
            "loading": _placeholder_photo(background, accent, accent, "…"),
            "failed": _placeholder_photo(background, border, muted, "×"),
        }

    # ------------------------------------------------------------------
    # Row indexing and rendering

    def _render_rows(self) -> None:
        super()._render_rows()
        if hasattr(self, "_card_rows"):
            self._reindex_card_rows()
            self._restore_row_art()
            self._queue_visible_portraits()

    def _reindex_card_rows(self) -> None:
        rows: dict[str, list[int]] = {}
        for index, record in enumerate(getattr(self, "records", ())):
            card_id = row_from_record(index, record).card_id
            if card_id:
                rows.setdefault(str(card_id), []).append(index)
        self._card_rows = {key: tuple(value) for key, value in rows.items()}

    def _restore_row_art(self) -> None:
        if not hasattr(self, "tree"):
            return
        for card_id in self._card_rows:
            path = self._cached_portrait(card_id)
            if path is not None:
                self._apply_portrait_to_rows(card_id, path)
            elif card_id in self._portrait_futures:
                self._apply_placeholder_to_rows(card_id, "loading")
            elif card_id in self._failed_cards:
                self._apply_placeholder_to_rows(card_id, "failed")
            else:
                self._apply_placeholder_to_rows(card_id, "empty")
        self._update_chrome_status()

    def _apply_portrait_to_rows(self, card_id: str, path: Path) -> None:
        photo = self._card_photos.get(card_id)
        if photo is None:
            photo = _photo(path, (34, 34))
            if photo is None:
                self._apply_placeholder_to_rows(card_id, "failed")
                return
            self._card_photos[card_id] = photo
        for index in self._card_rows.get(card_id, ()):
            item_id = f"record-{index}"
            if self.tree.exists(item_id):
                self.tree.item(item_id, image=photo)
                self._roster_portrait_photos[index] = photo

    def _apply_placeholder_to_rows(self, card_id: str, state: str) -> None:
        photo = self._placeholders.get(state)
        if photo is None:
            return
        for index in self._card_rows.get(card_id, ()):
            item_id = f"record-{index}"
            if self.tree.exists(item_id):
                self.tree.item(item_id, image=photo)

    # ------------------------------------------------------------------
    # Priority and automatic loading

    def _auto_preload_portraits(self) -> None:
        self._auto_preload_after = None
        self._enqueue_portraits(self._ordered_card_ids(), priority_visible=True)

    def preload_all_portraits(self) -> None:
        self._failed_cards.clear()
        self._enqueue_portraits(self._ordered_card_ids(), priority_visible=True)
        self._update_chrome_status()

    def _queue_visible_portraits(self, _event=None) -> None:
        if self._destroying:
            return
        if self._visible_preload_after is not None:
            try:
                self.after_cancel(self._visible_preload_after)
            except tk.TclError:
                pass
        self._visible_preload_after = self.after(90, self._load_visible_portraits)

    def _load_visible_portraits(self) -> None:
        self._visible_preload_after = None
        self._enqueue_portraits(self._visible_card_ids(), priority_visible=True)

    def _ordered_card_ids(self) -> tuple[str, ...]:
        selected: list[str] = []
        media = self._selected_media_ids()
        if media is not None:
            selected.append(str(media[0]))
        visible = list(self._visible_card_ids())
        all_cards = list(self._unique_card_ids())
        return tuple(dict.fromkeys((*selected, *visible, *all_cards)))

    def _visible_card_ids(self) -> tuple[str, ...]:
        visible: list[str] = []
        children = self.tree.get_children()
        for item_id in children:
            try:
                if not self.tree.bbox(item_id):
                    continue
                index = int(str(item_id).removeprefix("record-"))
            except (TypeError, ValueError, tk.TclError):
                continue
            if index < 0 or index >= len(self.records):
                continue
            card_id = row_from_record(index, self.records[index]).card_id
            if card_id:
                visible.append(str(card_id))
        if not visible:
            for item_id in children[:18]:
                try:
                    index = int(str(item_id).removeprefix("record-"))
                except ValueError:
                    continue
                card_id = row_from_record(index, self.records[index]).card_id
                if card_id:
                    visible.append(str(card_id))
        return tuple(dict.fromkeys(visible))

    def _enqueue_portraits(
        self,
        card_ids: tuple[str, ...],
        *,
        priority_visible: bool,
    ) -> None:
        visible = set(self._visible_card_ids()) if priority_visible else set()
        selected = self._selected_media_ids()
        selected_card = str(selected[0]) if selected is not None else ""
        for card_id in card_ids:
            priority = card_id == selected_card or card_id in visible
            self._enqueue_portrait(card_id, priority=priority)
        self._ensure_portrait_poller()
        self._update_chrome_status()

    def _enqueue_portrait(self, card_id: str, *, priority: bool) -> None:
        if not card_id:
            return
        cached = self._cached_portrait(card_id)
        if cached is not None:
            self._apply_portrait_to_rows(card_id, cached)
            return

        existing = self._portrait_futures.get(card_id)
        if existing is not None:
            if priority and existing.cancel():
                self._portrait_futures.pop(card_id, None)
            else:
                return

        executor = self._priority_executor if priority else self._background_executor
        future = executor.submit(self._load_portrait, card_id)
        self._portrait_futures[card_id] = future
        self._apply_placeholder_to_rows(card_id, "loading")
        future.add_done_callback(
            lambda completed, key=card_id: self._portrait_events.put(
                ("portrait", key, completed)
            )
        )

    def _load_portrait(self, card_id: str) -> PortraitLoadResult:
        # Use a task-local remote client. urllib openers keep mutable connection
        # state and should not be shared across worker threads.
        local = self._get_local_portrait_cache()
        remote = VeteranMediaCache(self._get_media_cache().root)
        return VeteranPortraitResolver(local, remote).resolve(card_id)

    # ------------------------------------------------------------------
    # Selected record portrait and skill icons

    def _request_primary_portrait(
        self,
        selection: tuple[str, tuple[int, ...]],
        *,
        force: bool = False,
    ) -> None:
        card_id, skill_ids = selection
        card_id = str(card_id)
        if force:
            self._failed_cards.discard(card_id)
            self._portrait_failures.discard(card_id)

        self._portrait_request = selection
        self.primary_portrait_button.configure(state="disabled", text="Loading…")
        self._enqueue_portrait(card_id, priority=True)
        self._request_selected_skill_icons(selection)
        self._ensure_portrait_poller()

    def _request_selected_skill_icons(
        self,
        selection: tuple[str, tuple[int, ...]],
    ) -> None:
        self._skill_generation += 1
        generation = self._skill_generation
        skill_ids = tuple(selection[1])
        if not skill_ids:
            return
        remote_root = self._get_media_cache().root
        future = self._priority_executor.submit(
            lambda: VeteranMediaCache(remote_root).fetch_selection(0, skill_ids)
        )
        self._skill_future = future
        future.add_done_callback(
            lambda completed: self._portrait_events.put(
                ("skills", generation, selection, completed)
            )
        )

    def _render_selected_cached_media(self) -> None:
        selection = self._selected_media_ids()
        if selection is None:
            return
        card_id, skill_ids = selection
        portrait = self._cached_portrait(card_id)
        cached_icons = self._get_media_cache().cached_selection(0, skill_ids)
        result = VeteranMediaResult(
            portrait=portrait,
            skill_icons=cached_icons.skill_icons,
            cache_hits=int(portrait is not None) + cached_icons.cache_hits,
            downloads=0,
        )
        _WorkspaceVeteranRosterPage._render_media(self, result)
        if portrait is not None:
            self._render_primary_portrait(portrait)
            self.primary_portrait_button.configure(
                state="normal",
                text="Reload portrait",
            )

    # ------------------------------------------------------------------
    # Worker event bridge. All Tk and ImageTk work stays on the main thread.

    def _ensure_portrait_poller(self) -> None:
        if self._portrait_event_after is None and not self._destroying:
            self._portrait_event_after = self.after(55, self._poll_portrait_events)

    def _poll_portrait_events(self) -> None:
        self._portrait_event_after = None
        while True:
            try:
                event = self._portrait_events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "portrait":
                self._consume_portrait_event(event[1], event[2])
            elif event[0] == "skills":
                self._consume_skill_event(event[1], event[2], event[3])

        if self._portrait_futures or (
            self._skill_future is not None and not self._skill_future.done()
        ):
            self._ensure_portrait_poller()
        self._update_chrome_status()

    def _consume_portrait_event(self, card_id: str, future: Future) -> None:
        current = self._portrait_futures.get(card_id)
        if current is not future:
            return
        self._portrait_futures.pop(card_id, None)
        try:
            result: PortraitLoadResult = future.result()
        except Exception:
            result = PortraitLoadResult(
                card_id=card_id,
                portrait=None,
                source="unavailable",
                warning="Portrait worker failed.",
            )

        if result.portrait is not None:
            self._failed_cards.discard(card_id)
            self._portrait_failures.discard(card_id)
            self._card_photos.pop(card_id, None)
            self._apply_portrait_to_rows(card_id, result.portrait)
        else:
            self._failed_cards.add(card_id)
            self._portrait_failures.add(card_id)
            self._apply_placeholder_to_rows(card_id, "failed")

        selected = self._selected_media_ids()
        if selected is not None and str(selected[0]) == card_id:
            if result.portrait is None:
                self.primary_portrait_label.configure(
                    image="",
                    text="Portrait unavailable\nUse Retry portrait",
                )
                self.primary_portrait_button.configure(
                    state="normal",
                    text="Retry portrait",
                )
            else:
                self._render_selected_cached_media()

    def _consume_skill_event(
        self,
        generation: int,
        selection: tuple[str, tuple[int, ...]],
        future: Future,
    ) -> None:
        if generation != self._skill_generation:
            return
        self._skill_future = None
        try:
            future.result()
        except Exception:
            return
        if self._selected_media_ids() == selection:
            self._render_selected_cached_media()

    # ------------------------------------------------------------------
    # Status, cache reset, and lifecycle

    def _update_chrome_status(self) -> None:
        if not hasattr(self, "chrome_status_value"):
            return
        card_ids = self._unique_card_ids()
        cached = sum(self._cached_portrait(card_id) is not None for card_id in card_ids)
        visible = len(getattr(self, "visible_rows", ()))
        total = len(getattr(self, "rows", ()))
        loading = len(self._portrait_futures)
        status = (
            f"{visible:,}/{total:,} veterans · "
            f"{cached:,}/{len(card_ids):,} portraits"
        )
        if loading:
            status += f" · {loading:,} loading"
        elif self._failed_cards:
            status += f" · {len(self._failed_cards):,} unavailable"
        self.chrome_status_value.set(status)

        host = getattr(self, "_portrait_progress_host", None)
        value = getattr(self, "_portrait_progress_value", None)
        label = getattr(self, "_portrait_progress_label_value", None)
        if host is not None and value is not None and label is not None:
            total_cards = max(1, len(card_ids))
            value.set(cached)
            for child in host.winfo_children():
                if isinstance(child, ttk.Progressbar):
                    child.configure(maximum=total_cards)
                    break
            label.set(f"{cached}/{len(card_ids)} ready")
            if loading:
                host.grid()
            else:
                host.grid_remove()

        if hasattr(self, "preload_portraits_button"):
            self.preload_portraits_button.configure(
                text=f"Loading portraits ({loading})" if loading else "Refresh portraits",
                state="disabled" if loading else "normal",
            )

    def clear_media_cache(self) -> None:
        super().clear_media_cache()
        self._card_photos.clear()
        self._failed_cards.clear()
        self._reindex_card_rows()
        self._restore_row_art()
        self._enqueue_portraits(self._ordered_card_ids(), priority_visible=True)

    def _shutdown_portrait_workers(self, event) -> None:
        if event.widget is not self or self._destroying:
            return
        self._destroying = True
        for callback_name in (
            "_portrait_event_after",
            "_auto_preload_after",
            "_visible_preload_after",
        ):
            callback = getattr(self, callback_name, None)
            if callback is not None:
                try:
                    self.after_cancel(callback)
                except tk.TclError:
                    pass
                setattr(self, callback_name, None)
        self._priority_executor.shutdown(wait=False, cancel_futures=True)
        self._background_executor.shutdown(wait=False, cancel_futures=True)


def _direct_child(parent: tk.Misc, descendant: tk.Misc) -> tk.Misc | None:
    current: tk.Misc | None = descendant
    while current is not None and current.master is not parent:
        current = current.master
    return current


def _placeholder_photo(
    background: tuple[int, int, int],
    border: tuple[int, int, int],
    foreground: tuple[int, int, int],
    symbol: str,
) -> ImageTk.PhotoImage:
    image = Image.new("RGBA", (34, 34), (*background, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 2, 31, 31), radius=7, outline=border, width=2)
    box = draw.textbbox((0, 0), symbol)
    width = box[2] - box[0]
    height = box[3] - box[1]
    draw.text(
        ((34 - width) / 2, (34 - height) / 2 - 1),
        symbol,
        fill=(*foreground, 255),
    )
    return ImageTk.PhotoImage(image)


def _photo(path: Path, size: tuple[int, int]) -> ImageTk.PhotoImage | None:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
            image.thumbnail(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
    except (OSError, ValueError, tk.TclError):
        return None

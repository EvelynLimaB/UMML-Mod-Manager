from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Callable

from .providers.gamebanana import GameBananaPage
from .providers.gamebanana_previews import PreviewGameBananaClient


class DiscoverExperienceActions:
    """Keep online discovery useful without turning it into a modal task."""

    def configure_discover_experience(self) -> None:
        if getattr(self, "_discover_experience_configured", False):
            return
        self._discover_experience_configured = True
        self._gb_catalog_loading = False
        self._gb_catalog_serial = 0
        self._gb_catalog_request_signature: tuple[str, str, str, int] | None = None
        self._gb_initial_attempted = False
        self._gb_initial_scheduled = False
        self._gb_loaded_at = ""
        self._gb_last_region_value = self.gb_region.get().strip().casefold()

        self.discover.browse_button.configure(text="Refresh")
        self.discover.gb_meta.configure(
            text=(
                "Latest mods load automatically. Change region or sorting to refresh; "
                "press Enter to run a text search."
            )
        )
        self.discover.gb_sort_box.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.gamebanana_filter_changed(),
            add="+",
        )
        self._gb_region_trace = self.gb_region.trace_add(
            "write",
            self._gamebanana_region_changed,
        )

        parent = self.discover.gb_tree.master
        self._gb_catalog_message = ttk.Label(
            parent,
            text="Loading the latest GameBanana mods automatically…",
            style="SurfaceMuted.TLabel",
            anchor="center",
            justify="center",
            wraplength=520,
            padding=24,
        )
        self._gb_catalog_message.grid(row=0, column=0, sticky="nsew")
        self._gb_catalog_message.tkraise()

        for tree in (
            self.library.tree,
            self.discover.gb_tree,
            self.discover.local_tree,
        ):
            self._add_tree_horizontal_scrollbar(tree)
        self._add_text_scrollbars(self.plan_text)

    @staticmethod
    def _add_tree_horizontal_scrollbar(tree) -> None:
        if getattr(tree, "_umm_horizontal_scrollbar", None) is not None:
            return
        parent = tree.master
        scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=scrollbar.set)
        scrollbar.grid(row=1, column=0, sticky="ew")
        tree._umm_horizontal_scrollbar = scrollbar

    @staticmethod
    def _add_text_scrollbars(widget: tk.Text) -> None:
        if getattr(widget, "_umm_scrollbars", None) is not None:
            return
        parent = widget.master
        vertical = ttk.Scrollbar(parent, orient="vertical", command=widget.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=widget.xview)
        widget.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.grid(row=1, column=1, sticky="ns")
        horizontal.grid(row=2, column=0, sticky="ew")
        widget._umm_scrollbars = (vertical, horizontal)

    def _gamebanana_filter_signature(self) -> tuple[str, str, str]:
        return (
            self.gb_region.get().strip().casefold() or "global",
            self.gb_sort.get().strip().casefold() or "updated",
            self.gb_query.get().strip(),
        )

    def _gamebanana_request_signature(self) -> tuple[str, str, str, int]:
        return (*self._gamebanana_filter_signature(), max(1, int(self.gb_page)))

    def _gamebanana_region_changed(self, *_args) -> None:
        current = self.gb_region.get().strip().casefold() or "global"
        if current == getattr(self, "_gb_last_region_value", ""):
            return
        self._gb_last_region_value = current
        if getattr(self, "_auto_network_enabled", True):
            self.gamebanana_filter_changed()

    def schedule_initial_gamebanana_load(self, delay: int = 650) -> None:
        if (
            getattr(self, "_closing", False)
            or getattr(self, "_gb_initial_scheduled", False)
        ):
            return
        self._gb_initial_scheduled = True
        try:
            self.root.after(delay, self.ensure_gamebanana_catalog)
        except tk.TclError:
            self._closing = True

    def ensure_gamebanana_catalog(self) -> None:
        if (
            getattr(self, "_closing", False)
            or getattr(self, "_gb_catalog_loading", False)
            or getattr(self, "_gb_initial_attempted", False)
            or bool(getattr(self, "gb_results", {}))
        ):
            return
        self.browse_gamebanana()

    def discover_page_activated(self) -> None:
        if getattr(self, "_gb_catalog_loading", False):
            self._set_discover_status("Refreshing the GameBanana catalogue…")
            return
        if self.gb_results:
            suffix = f" · updated {self._gb_loaded_at}" if self._gb_loaded_at else ""
            self._set_discover_status(
                f"{len(self.gb_results)} GameBanana mod(s) loaded{suffix}"
            )
            return
        if getattr(self, "_gb_initial_attempted", False):
            self._set_discover_status(
                "GameBanana has not loaded yet. Refresh to retry; local imports still work."
            )
            return
        self._set_discover_status("Loading the latest GameBanana mods automatically…")
        self.ensure_gamebanana_catalog()

    def _set_discover_status(self, message: str) -> None:
        if getattr(self, "_current_page", "discover") == "discover":
            self.status.set(message)

    def gamebanana_filter_changed(self) -> None:
        self.gb_page = 1
        self.save_settings(silent=True)
        self.browse_gamebanana()

    def browse_gamebanana(self) -> None:
        if getattr(self, "_closing", False):
            return

        filter_signature = self._gamebanana_filter_signature()
        previous = getattr(self, "_gb_browse_signature", None)
        if previous is not None and previous != filter_signature:
            self.gb_page = 1
        self._gb_browse_signature = filter_signature
        request_signature = self._gamebanana_request_signature()

        if getattr(self, "_gb_catalog_loading", False):
            if request_signature == getattr(
                self,
                "_gb_catalog_request_signature",
                None,
            ):
                return
            # A programmatic region change can occur while startup discovery is
            # running. Invalidate that response and immediately request the new
            # catalogue rather than displaying data under the wrong filter.
            self._gb_catalog_serial = getattr(self, "_gb_catalog_serial", 0) + 1
            self._gb_catalog_loading = False

        self._gb_initial_attempted = True
        self._gb_catalog_loading = True
        self._gb_catalog_serial = getattr(self, "_gb_catalog_serial", 0) + 1
        token = self._gb_catalog_serial
        self._gb_catalog_request_signature = request_signature
        if not self.gb_results:
            self._set_gamebanana_catalog_state(
                "Loading the latest GameBanana mods…\n\n"
                "You can keep using Library, Studio, and local imports."
            )
        self._set_discover_status("Refreshing the GameBanana catalogue…")
        self.discover.browse_button.configure(text="Loading…", state="disabled")
        self.refresh_action_states()

        region, sort, query, page_number = request_signature

        def worker() -> None:
            try:
                page = PreviewGameBananaClient().browse(
                    region=region,
                    page=page_number,
                    sort=sort,
                    query=query,
                )
            except Exception as exc:
                self._schedule_gamebanana_catalog_callback(
                    token,
                    lambda error=exc: self._gamebanana_catalog_failed(
                        token,
                        request_signature,
                        error,
                    ),
                )
            else:
                self._schedule_gamebanana_catalog_callback(
                    token,
                    lambda value=page: self._gamebanana_catalog_loaded(
                        token,
                        request_signature,
                        value,
                    ),
                )

        threading.Thread(
            target=worker,
            name=f"umm-gamebanana-catalog-{token}",
            daemon=True,
        ).start()

    def _schedule_gamebanana_catalog_callback(
        self,
        token: int,
        callback: Callable[[], None],
    ) -> None:
        if (
            getattr(self, "_closing", False)
            or token != getattr(self, "_gb_catalog_serial", -1)
        ):
            return
        try:
            self.root.after(0, callback)
        except tk.TclError:
            self._closing = True

    def _catalog_callback_is_current(
        self,
        token: int,
        request_signature: tuple[str, str, str, int],
    ) -> bool:
        return bool(
            not getattr(self, "_closing", False)
            and token == getattr(self, "_gb_catalog_serial", -1)
            and request_signature
            == getattr(self, "_gb_catalog_request_signature", None)
        )

    def _gamebanana_catalog_loaded(
        self,
        token: int,
        request_signature: tuple[str, str, str, int],
        page: GameBananaPage,
    ) -> None:
        if not self._catalog_callback_is_current(token, request_signature):
            return
        if request_signature != self._gamebanana_request_signature():
            self._gb_catalog_loading = False
            self.browse_gamebanana()
            return

        previous_selection = self.discover.gb_tree.selection()
        previous_id = previous_selection[0] if previous_selection else ""
        self._gb_catalog_loading = False
        self._show_gamebanana_page(page)
        self._gb_loaded_at = datetime.now().strftime("%H:%M")

        children = self.discover.gb_tree.get_children()
        if children:
            selected = previous_id if previous_id in children else children[0]
            self._clear_gamebanana_catalog_state()
            self.discover.gb_tree.selection_set(selected)
            self.discover.gb_tree.focus(selected)
            self.discover.gb_tree.see(selected)
            self.select_gamebanana_mod()
            self._set_discover_status(
                f"Loaded {len(page.mods)} GameBanana mod(s) · updated {self._gb_loaded_at}"
            )
        else:
            query = self.gb_query.get().strip()
            self._set_gamebanana_catalog_state(
                "No matching mods were returned."
                + (f"\n\nSearch: {query}" if query else "")
                + "\n\nChange the filters or press Refresh."
            )
            self._set_discover_status("GameBanana returned no matching mods")
        self.discover.browse_button.configure(text="Refresh")
        self.refresh_action_states()

    def _gamebanana_catalog_failed(
        self,
        token: int,
        request_signature: tuple[str, str, str, int],
        error: Exception,
    ) -> None:
        if not self._catalog_callback_is_current(token, request_signature):
            return
        if request_signature != self._gamebanana_request_signature():
            self._gb_catalog_loading = False
            self.browse_gamebanana()
            return

        self._gb_catalog_loading = False
        message = " ".join(str(error).split())
        if len(message) > 180:
            message = message[:177] + "…"
        if self.gb_results:
            self._set_discover_status(
                "Could not refresh GameBanana; keeping the current results. " + message
            )
        else:
            self._set_gamebanana_catalog_state(
                "GameBanana is temporarily unavailable.\n\n"
                "Press Refresh to retry. Local folders and imported mods still work.\n\n"
                + message
            )
            self.discover.page_label.configure(text="Catalogue unavailable")
            self._set_discover_status(
                "GameBanana could not be reached; no local or game files changed"
            )
        self.discover.browse_button.configure(text="Retry")
        self.refresh_action_states()

    def _show_gamebanana_page(self, page: GameBananaPage) -> None:
        """Render catalogue data without overwriting another page's footer."""

        tree = self.discover.gb_tree
        tree.delete(*tree.get_children())
        self.gb_results = {}
        self._clear_gamebanana_selection()
        for mod in page.mods:
            key = str(mod.id)
            self.gb_results[key] = mod
            tree.insert(
                "",
                "end",
                iid=key,
                text=mod.name,
                values=(
                    mod.author,
                    mod.version or "—",
                    f"{mod.downloads:,}",
                ),
            )
        self.gb_page = page.page
        self.discover.page_label.configure(
            text=f"Page {page.page}"
            + (f" • {page.total} records" if page.total else "")
        )
        self._gb_can_previous = page.page > 1
        self._gb_can_next = bool(page.has_more)

    def _set_gamebanana_catalog_state(self, message: str) -> None:
        label = getattr(self, "_gb_catalog_message", None)
        if label is None:
            return
        label.configure(text=message)
        label.grid()
        label.tkraise()

    def _clear_gamebanana_catalog_state(self) -> None:
        label = getattr(self, "_gb_catalog_message", None)
        if label is not None:
            label.grid_remove()

    def change_gamebanana_page(self, delta: int) -> None:
        target = self.gb_page + delta
        if target < 1 or getattr(self, "_gb_catalog_loading", False):
            return
        self.gb_page = target
        self.browse_gamebanana()

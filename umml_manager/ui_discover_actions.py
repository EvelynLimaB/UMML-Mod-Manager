from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from collections import OrderedDict
from pathlib import Path
from tkinter import filedialog
from typing import Callable

from .discovery import ModCandidate, default_search_roots, scan_mod_candidates
from .preview_images import PreviewImage, PreviewImageLoader
from .providers.gamebanana import GameBananaMod, GameBananaPage
from .providers.gamebanana_previews import PreviewGameBananaClient
from .studio import open_path


class DiscoverActions:
    def browse_gamebanana(self):
        self._run_task(
            "Browsing Umamusume GameBanana…",
            lambda: PreviewGameBananaClient().browse(
                region=self.gb_region.get(),
                page=self.gb_page,
                sort=self.gb_sort.get(),
                query=self.gb_query.get(),
            ),
            self._show_gamebanana_page,
        )

    def _preview_runtime(self) -> tuple[int, OrderedDict[str, PreviewImage]]:
        if not hasattr(self, "_gb_preview_serial"):
            self._gb_preview_serial = 0
        if not hasattr(self, "_gb_preview_cache"):
            self._gb_preview_cache = OrderedDict()
        return self._gb_preview_serial, self._gb_preview_cache

    def _detail_runtime(self) -> int:
        if not hasattr(self, "_gb_detail_serial"):
            self._gb_detail_serial = 0
        return self._gb_detail_serial

    def _cancel_gamebanana_preview(self) -> None:
        serial, _cache = self._preview_runtime()
        self._gb_preview_serial = serial + 1

    def _cancel_gamebanana_details(self) -> None:
        self._gb_detail_serial = self._detail_runtime() + 1

    def _clear_gamebanana_selection(self):
        self._cancel_gamebanana_preview()
        self._cancel_gamebanana_details()
        self.gb_selected = None
        self.discover.gb_title.configure(text="Select a mod")
        self.discover.gb_meta.configure(
            text="Choose a result to inspect its files and metadata."
        )
        self.discover.gb_stats.configure(text="")
        self.discover.set_gb_preview_state("Select a mod to load its preview.")
        self.discover.set_gb_description("")
        self.discover.gb_files.configure(values=(), state="readonly")
        self.discover.gb_files.set("")
        self.discover.open_gb_button.configure(state="disabled")
        self.discover.install_gb_button.configure(
            text="Install",
            state="disabled",
        )

    def _show_gamebanana_page(self, page: GameBananaPage):
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
        self.discover.prev_button.configure(
            state="normal" if page.page > 1 else "disabled"
        )
        self.discover.next_button.configure(
            state="normal" if page.has_more else "disabled"
        )
        self.status.set(f"Loaded {len(page.mods)} GameBanana mod(s)")

    def select_gamebanana_mod(self):
        selected = self.discover.gb_tree.selection()
        if not selected:
            self._clear_gamebanana_selection()
            return
        mod = self.gb_results.get(selected[0])
        if not mod:
            self._clear_gamebanana_selection()
            return

        self._cancel_gamebanana_details()
        self.gb_selected = mod
        self._render_gamebanana_mod(mod)
        self._configure_gamebanana_files(
            mod,
            details_complete=bool(mod.files),
            loading=not mod.files,
        )
        self.discover.open_gb_button.configure(state="normal")
        self._load_gamebanana_preview(mod.id, mod.image_url)
        if not mod.files:
            self._load_gamebanana_details(mod.id)

    def _render_gamebanana_mod(self, mod: GameBananaMod) -> None:
        self.discover.gb_title.configure(text=mod.name)
        self.discover.gb_meta.configure(
            text=f"{mod.author or 'Unknown author'} • {mod.category or 'Mod'} • "
            f"{mod.version or 'Unversioned'}"
        )
        self.discover.gb_stats.configure(
            text=f"{mod.downloads:,} downloads • {mod.likes:,} likes • "
            f"{mod.views:,} views"
        )
        self.discover.set_gb_description(
            mod.description or "No description was returned by GameBanana."
        )

    def _configure_gamebanana_files(
        self,
        mod: GameBananaMod,
        *,
        details_complete: bool,
        loading: bool = False,
    ) -> None:
        if mod.files:
            self.discover.gb_files.configure(
                values=[
                    f"{item.id} — {item.name} ({item.downloads:,} downloads)"
                    for item in mod.files
                ],
                state="readonly",
            )
            self.discover.gb_files.current(0)
            self.discover.install_gb_button.configure(
                text="Install",
                state="normal",
            )
            return

        if details_complete:
            self.discover.gb_files.configure(
                values=("No downloadable files were published.",),
                state="disabled",
            )
            self.discover.gb_files.set("No downloadable files were published.")
            self.discover.install_gb_button.configure(
                text="No files",
                state="disabled",
            )
            return

        message = (
            "Latest available file (loading details…)"
            if loading
            else "Latest available file (details reload during install)"
        )
        self.discover.gb_files.configure(
            values=(message,),
            state="readonly",
        )
        self.discover.gb_files.current(0)
        self.discover.install_gb_button.configure(
            text="Install latest",
            state="normal",
        )

    def _load_gamebanana_details(self, mod_id: int) -> None:
        self._cancel_gamebanana_details()
        token = self._detail_runtime()
        self.status.set("Loading GameBanana file list…")

        def worker() -> None:
            try:
                detailed = PreviewGameBananaClient().fetch(str(mod_id))
            except Exception as exc:
                self._schedule_detail_callback(
                    token,
                    lambda error=exc: self._show_failed_gamebanana_details(
                        token,
                        mod_id,
                        error,
                    ),
                )
            else:
                self._schedule_detail_callback(
                    token,
                    lambda value=detailed: self._show_loaded_gamebanana_details(
                        token,
                        mod_id,
                        value,
                    ),
                )

        threading.Thread(
            target=worker,
            name=f"umml-gamebanana-details-{mod_id}-{token}",
            daemon=True,
        ).start()

    def _schedule_detail_callback(
        self,
        token: int,
        callback: Callable[[], None],
    ) -> None:
        if self._closing or token != getattr(self, "_gb_detail_serial", -1):
            return
        try:
            self.root.after(0, callback)
        except tk.TclError:
            self._closing = True

    def _detail_is_current(self, token: int, mod_id: int) -> bool:
        selected = self.gb_selected
        return bool(
            not self._closing
            and token == getattr(self, "_gb_detail_serial", -1)
            and selected is not None
            and selected.id == mod_id
            and str(mod_id) in self.gb_results
        )

    def _show_loaded_gamebanana_details(
        self,
        token: int,
        mod_id: int,
        detailed: GameBananaMod,
    ) -> None:
        if not self._detail_is_current(token, mod_id):
            return
        previous = self.gb_selected
        previous_image = previous.image_url if previous is not None else ""
        self.gb_results[str(mod_id)] = detailed
        self.gb_selected = detailed
        self._render_gamebanana_mod(detailed)
        self._configure_gamebanana_files(
            detailed,
            details_complete=True,
        )
        if detailed.files:
            self.status.set(
                f"Loaded {len(detailed.files)} downloadable file(s) for "
                f"{detailed.name}"
            )
        else:
            self.status.set(f"{detailed.name} has no downloadable files")
        if detailed.image_url != previous_image:
            self._load_gamebanana_preview(detailed.id, detailed.image_url)

    def _show_failed_gamebanana_details(
        self,
        token: int,
        mod_id: int,
        error: Exception,
    ) -> None:
        if not self._detail_is_current(token, mod_id):
            return
        selected = self.gb_selected
        if selected is not None:
            self._configure_gamebanana_files(
                selected,
                details_complete=False,
                loading=False,
            )
        message = " ".join(str(error).split())
        if len(message) > 100:
            message = message[:97] + "…"
        self.status.set(
            "Could not pre-load the GameBanana file list. "
            f"Install latest will retry. {message}"
        )

    def _load_gamebanana_preview(self, mod_id: int, image_url: str) -> None:
        self._cancel_gamebanana_preview()
        serial, cache = self._preview_runtime()
        token = serial
        if not image_url:
            self.discover.set_gb_preview_state(
                "No preview image was returned for this mod."
            )
            return

        cached = cache.get(image_url)
        if cached is not None:
            cache.move_to_end(image_url)
            self._show_loaded_gamebanana_preview(token, mod_id, image_url, cached)
            return

        self.discover.set_gb_preview_state("Loading preview…")

        def worker() -> None:
            try:
                preview = PreviewImageLoader().load(image_url)
            except Exception as exc:
                self._schedule_preview_callback(
                    token,
                    lambda error=exc: self._show_failed_gamebanana_preview(
                        token,
                        mod_id,
                        image_url,
                        error,
                    ),
                )
            else:
                self._schedule_preview_callback(
                    token,
                    lambda value=preview: self._show_loaded_gamebanana_preview(
                        token,
                        mod_id,
                        image_url,
                        value,
                    ),
                )

        threading.Thread(
            target=worker,
            name=f"umml-preview-{mod_id}-{token}",
            daemon=True,
        ).start()

    def _schedule_preview_callback(
        self,
        token: int,
        callback: Callable[[], None],
    ) -> None:
        if self._closing or token != getattr(self, "_gb_preview_serial", -1):
            return
        try:
            self.root.after(0, callback)
        except tk.TclError:
            self._closing = True

    def _preview_is_current(self, token: int, mod_id: int, image_url: str) -> bool:
        selected = self.gb_selected
        return bool(
            not self._closing
            and token == getattr(self, "_gb_preview_serial", -1)
            and selected is not None
            and selected.id == mod_id
            and selected.image_url == image_url
            and str(mod_id) in self.gb_results
        )

    def _show_loaded_gamebanana_preview(
        self,
        token: int,
        mod_id: int,
        image_url: str,
        preview: PreviewImage,
    ) -> None:
        if not self._preview_is_current(token, mod_id, image_url):
            return
        _serial, cache = self._preview_runtime()
        cache[image_url] = preview
        cache.move_to_end(image_url)
        while len(cache) > 24:
            cache.popitem(last=False)
        size_kib = max(1, round(preview.byte_size / 1024))
        self.discover.set_gb_preview_image(
            preview.image,
            source=f"GameBanana preview • {size_kib:,} KiB",
        )

    def _show_failed_gamebanana_preview(
        self,
        token: int,
        mod_id: int,
        image_url: str,
        error: Exception,
    ) -> None:
        if not self._preview_is_current(token, mod_id, image_url):
            return
        message = " ".join(str(error).split())
        if len(message) > 120:
            message = message[:117] + "…"
        self.discover.set_gb_preview_state(
            "Preview unavailable. The mod can still be inspected and installed.",
            source=message,
        )

    def change_gamebanana_page(self, delta: int):
        target = self.gb_page + delta
        if target < 1:
            return
        self.gb_page = target
        self.browse_gamebanana()

    def install_gamebanana_mod(self):
        mod = self.gb_selected
        if not mod or str(mod.id) not in self.gb_results:
            self._clear_gamebanana_selection()
            return
        file_id = None
        selected = self.discover.gb_files.get()
        if selected:
            try:
                file_id = int(selected.split("—", 1)[0].strip())
            except ValueError:
                pass
        self._run_task(
            f"Downloading {mod.name}…",
            lambda: PreviewGameBananaClient().import_mod(
                self.store,
                str(mod.id),
                file_id=file_id,
            ),
            self._finish_import,
        )

    def open_gamebanana_page(self):
        if self.gb_selected and str(self.gb_selected.id) in self.gb_results:
            webbrowser.open(self.gb_selected.profile_url)

    def add_scan_root(self):
        path = filedialog.askdirectory(parent=self.root)
        if not path:
            return
        values = [
            item.strip() for item in self.scan_roots.get().split(";") if item.strip()
        ]
        if path not in values:
            values.append(path)
            self.scan_roots.set("; ".join(values))
        self.save_settings(silent=True)

    def scan_local_mods(self):
        roots = [
            Path(item.strip()).expanduser()
            for item in self.scan_roots.get().split(";")
            if item.strip()
        ]
        self._run_task(
            "Scanning for mod folders and archives…",
            lambda: scan_mod_candidates(roots or default_search_roots()),
            self._show_local_candidates,
        )

    def _show_local_candidates(self, candidates: list[ModCandidate]):
        tree = self.discover.local_tree
        tree.delete(*tree.get_children())
        self.local_candidates = {}
        for index, candidate in enumerate(candidates):
            key = str(index)
            self.local_candidates[key] = candidate
            tree.insert(
                "",
                "end",
                iid=key,
                text=candidate.name,
                values=(
                    candidate.kind,
                    candidate.confidence,
                    candidate.reason,
                    str(candidate.path),
                ),
            )
        self.status.set(f"Detected {len(candidates)} local mod candidate(s)")

    def selected_local_candidate(self):
        selected = self.discover.local_tree.selection()
        return self.local_candidates.get(selected[0]) if selected else None

    def open_local_candidate(self):
        candidate = self.selected_local_candidate()
        if candidate:
            open_path(
                candidate.path.parent if candidate.kind == "archive" else candidate.path
            )

    def import_local_candidate(self):
        candidate = self.selected_local_candidate()
        if candidate:
            self._import(
                lambda: self.store.import_archive(candidate.path)
                if candidate.kind == "archive"
                else self.store.import_folder(candidate.path)
            )

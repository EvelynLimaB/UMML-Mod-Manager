from __future__ import annotations

import argparse
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .discovery import default_search_roots
from .models import PACKAGE_UMML_ASSETS
from .providers.gamebanana import GameBananaMod
from .safety import hash_file
from .store import ManagerStore, default_root
from .ui_auto_prepare_actions import AutoPrepareActions
from .ui_discover import DiscoverPage
from .ui_discover_actions import DiscoverActions
from .ui_library import LibraryPage
from .ui_library_actions import LibraryActions
from .ui_settings import SettingsPage
from .ui_studio import StudioPage
from .ui_system_actions import SystemActions
from .ui_theme import BACKGROUND, SURFACE, TEXT, configure_theme

PRODUCT_NAME = "Uma Mod Manager"


class ManagerGUI(
    AutoPrepareActions,
    LibraryActions,
    DiscoverActions,
    SystemActions,
):
    def __init__(self, root: tk.Tk, store: ManagerStore | None = None):
        self.root = root
        self.store = store or ManagerStore(default_root())
        self._closing = False
        self._busy = False
        self._game_running = False
        self._task_serial = 0
        self._nav_buttons = {}
        self._gb_install_enabled = False
        self._gb_install_text = "Install"
        self._gb_can_previous = False
        self._gb_can_next = False
        self._saving_detected_installation = False
        settings = self.store.load_settings()
        self.profile_name = tk.StringVar(
            value=str(settings.get("profile", "Default"))
        )
        self.dat_path = tk.StringVar(
            value=str(settings.get("dat_path", ""))
        )
        self.meta_path = tk.StringVar(
            value=str(settings.get("meta_path", ""))
        )
        self.game_dir = tk.StringVar(
            value=str(settings.get("game_dir", ""))
        )
        self.region = tk.StringVar(
            value=str(settings.get("region", "global"))
        )
        self.installation_key = tk.StringVar(
            value=str(settings.get("installation_key", ""))
        )
        self.metadata_fingerprint = tk.StringVar(
            value=str(settings.get("metadata_fingerprint", ""))
        )
        self.installation_status = tk.StringVar(
            value="Checking saved installation settings…"
        )
        self.search_library = tk.StringVar()
        self.status = tk.StringVar(value="Ready")
        self.page_title = tk.StringVar(value="Library")
        self.game_status = tk.StringVar(value="Game status: checking…")
        self.gb_region = tk.StringVar(
            value=str(
                settings.get("gamebanana_region", self.region.get())
            )
        )
        self.gb_sort = tk.StringVar(value="updated")
        self.gb_query = tk.StringVar()
        self.gb_page = 1
        self.gb_results: dict[str, GameBananaMod] = {}
        self.gb_selected: GameBananaMod | None = None
        roots = settings.get("scan_roots") or [
            str(path) for path in default_search_roots()
        ]
        self.scan_roots = tk.StringVar(
            value="; ".join(str(item) for item in roots)
        )
        self.local_candidates = {}

        root.title(PRODUCT_NAME)
        root.geometry("1220x780")
        root.minsize(980, 650)
        root.configure(background=BACKGROUND)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        root.protocol("WM_DELETE_WINDOW", self.close)
        configure_theme(root)
        self._build_header()
        self._build_body()
        self._build_footer()
        self.refresh()
        self.show_page("library")
        self._refresh_game_status()
        self.refresh_action_states()
        if self.store.settings_warning:
            self.status.set(
                "Settings were reset and preserved; Run diagnostics for the path"
            )
        if self._saved_installation_is_ready():
            self.installation_status.set("Using saved installation paths.")
        else:
            self.installation_status.set(
                "No complete saved installation. Auto-detection is starting…"
            )
            self.root.after(
                300,
                lambda: self.autofill_installation(automatic=True)
                if not self._closing
                else None,
            )

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._task_serial += 1
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        self.root.destroy()

    def _saved_installation_is_ready(self) -> bool:
        try:
            return (
                Path(self.dat_path.get()).is_dir()
                and Path(self.game_dir.get()).is_dir()
                and Path(self.meta_path.get()).is_file()
            )
        except (OSError, ValueError):
            return False

    def _build_header(self):
        header = ttk.Frame(self.root, padding=(22, 15, 22, 12))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="UMA MOD", style="Title.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(
            header,
            textvariable=self.page_title,
            style="PageTitle.TLabel",
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))
        badges = ttk.Frame(header)
        badges.grid(row=0, column=2, sticky="e")
        self.profile_badge = ttk.Label(
            badges,
            text="Profile: Default",
            style="Badge.TLabel",
        )
        self.profile_badge.pack(side="left", padx=4)
        self.game_badge = ttk.Label(
            badges,
            textvariable=self.game_status,
            style="Warning.Badge.TLabel",
        )
        self.game_badge.pack(side="left", padx=4)

    def _build_body(self):
        body = ttk.Frame(self.root)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(
            body,
            style="Sidebar.TFrame",
            padding=(10, 18),
        )
        sidebar.grid(row=0, column=0, sticky="ns")
        for key, label in (
            ("library", "Library"),
            ("discover", "Discover"),
            ("studio", "Studio"),
            ("conflicts", "Conflicts"),
            ("settings", "Settings"),
        ):
            button = ttk.Button(
                sidebar,
                text=label,
                style="Nav.TButton",
                width=18,
                command=lambda item=key: self.show_page(item),
            )
            button.pack(fill="x", pady=2)
            self._nav_buttons[key] = button
        ttk.Separator(sidebar).pack(fill="x", pady=14)
        self.sidebar_diagnostics_button = ttk.Button(
            sidebar,
            text="Run diagnostics",
            style="Nav.TButton",
            command=self.run_diagnostics,
        )
        self.sidebar_diagnostics_button.pack(fill="x")

        self.content = ttk.Frame(body, padding=(18, 8, 22, 18))
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.library = LibraryPage(self.content, self)
        self.discover = DiscoverPage(self.content, self)
        self.studio = StudioPage(self.content, self)
        self.conflicts = self._build_conflicts_page()
        self.settings = SettingsPage(self.content, self)
        self.pages = {
            "library": self.library,
            "discover": self.discover,
            "studio": self.studio,
            "conflicts": self.conflicts,
            "settings": self.settings,
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

    def _build_conflicts_page(self):
        page = ttk.Frame(self.content)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        top = ttk.Frame(page)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            top,
            text="Resolved profile plan and file ownership",
            style="Muted.TLabel",
        ).pack(side="left")
        self.refresh_plan_button = ttk.Button(
            top,
            text="Refresh plan",
            style="Accent.TButton",
            command=self.render_plan,
        )
        self.refresh_plan_button.pack(side="right")
        self.plan_text = tk.Text(
            page,
            wrap="none",
            background=SURFACE,
            foreground=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
            font=("TkFixedFont", 10),
        )
        self.plan_text.grid(row=1, column=0, sticky="nsew")
        self.plan_text.configure(state="disabled")
        return page

    def _build_footer(self):
        footer = ttk.Frame(self.root, padding=(22, 7, 22, 12))
        footer.grid(row=2, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)
        ttk.Label(
            footer,
            textvariable=self.status,
            style="Muted.TLabel",
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.progress = ttk.Progressbar(
            footer,
            mode="indeterminate",
            length=210,
        )
        self.progress.grid(row=0, column=1, sticky="e")

    @staticmethod
    def _configure_button(widget, *, enabled: bool, text: str | None = None) -> None:
        values = {"state": "normal" if enabled else "disabled"}
        if text is not None:
            values["text"] = text
        widget.configure(**values)

    def refresh_action_states(self) -> None:
        if self._closing or not hasattr(self, "library"):
            return
        busy = bool(self._busy)
        game_running = bool(self._game_running)

        self.library.profile_box.configure(state="disabled" if busy else "readonly")
        self.library.search_entry.configure(state="disabled" if busy else "normal")
        for button in (
            self.library.new_profile_button,
            self.library.search_button,
            self.library.import_folder_button,
            self.library.import_archive_button,
            self.library.preview_conflicts_button,
        ):
            self._configure_button(button, enabled=not busy)

        selected_id = self.library.selected_id()
        record = None
        profile = None
        try:
            profile = self.profile()
            record = self.store.get_mod(selected_id) if selected_id else None
        except Exception:
            record = None

        selected_enabled = bool(
            record is not None and profile is not None and record.id in profile.enabled
        )
        enabled_index = (
            profile.enabled.index(record.id)
            if selected_enabled and profile is not None and record is not None
            else -1
        )
        self._configure_button(
            self.library.toggle_button,
            enabled=record is not None and not busy,
            text="Disable" if selected_enabled else "Enable",
        )
        self._configure_button(
            self.library.move_up_button,
            enabled=selected_enabled and enabled_index > 0 and not busy,
        )
        self._configure_button(
            self.library.move_down_button,
            enabled=(
                selected_enabled
                and profile is not None
                and enabled_index < len(profile.enabled) - 1
                and not busy
            ),
        )

        metadata_ready = False
        try:
            metadata_ready = Path(self.meta_path.get()).expanduser().is_file()
        except (OSError, ValueError):
            pass
        prepared = bool(record and record.files and record.prepared_path)
        stale = bool(
            prepared
            and self.metadata_fingerprint.get()
            and record is not None
            and record.prepared_against
            and self.metadata_fingerprint.get().casefold()
            != record.prepared_against.casefold()
        )
        prepare_text = "Prepare now"
        if prepared:
            prepare_text = "Re-prepare" if stale else "Re-prepare"
        self._configure_button(
            self.library.prepare_button,
            enabled=(
                record is not None
                and record.package_type == PACKAGE_UMML_ASSETS
                and metadata_ready
                and not busy
            ),
            text=prepare_text,
        )
        self._configure_button(
            self.library.workspace_button,
            enabled=record is not None and not busy,
        )
        self._configure_button(
            self.library.remove_button,
            enabled=record is not None and not busy,
        )

        blockers = True
        try:
            blockers = bool(self.current_resolution().blocking_issues)
        except Exception:
            blockers = True
        dat_ready = False
        try:
            dat_ready = Path(self.dat_path.get()).expanduser().is_dir()
        except (OSError, ValueError):
            pass
        if game_running:
            apply_text = "Close game to apply"
        elif blockers:
            apply_text = "Fix blockers to apply"
        elif not dat_ready:
            apply_text = "Set game data to apply"
        else:
            apply_text = "Apply profile"
        self._configure_button(
            self.library.apply_button,
            enabled=not busy and not game_running and not blockers and dat_ready,
            text=apply_text,
        )

        self.discover.gb_region_box.configure(state="disabled" if busy else "readonly")
        self.discover.gb_sort_box.configure(state="disabled" if busy else "readonly")
        self.discover.gb_query_entry.configure(state="disabled" if busy else "normal")
        self._configure_button(self.discover.browse_button, enabled=not busy)
        selected_gb = bool(
            self.gb_selected is not None
            and str(self.gb_selected.id) in self.gb_results
        )
        self._configure_button(
            self.discover.open_gb_button,
            enabled=selected_gb,
        )
        self._configure_button(
            self.discover.install_gb_button,
            enabled=selected_gb and self._gb_install_enabled and not busy,
            text=self._gb_install_text,
        )
        self._configure_button(
            self.discover.prev_button,
            enabled=self._gb_can_previous and not busy,
        )
        self._configure_button(
            self.discover.next_button,
            enabled=self._gb_can_next and not busy,
        )
        self.discover.scan_roots_entry.configure(state="disabled" if busy else "normal")
        self._configure_button(self.discover.add_folder_button, enabled=not busy)
        self._configure_button(self.discover.scan_button, enabled=not busy)
        local_selected = self.selected_local_candidate() is not None
        self._configure_button(
            self.discover.open_local_button,
            enabled=local_selected,
        )
        self._configure_button(
            self.discover.import_local_button,
            enabled=local_selected and not busy,
        )

        for button in (
            self.settings.autodetect_button,
            self.settings.dat_browse_button,
            self.settings.meta_browse_button,
            self.settings.game_browse_button,
            self.settings.save_button,
            self.settings.diagnostics_button,
            self.settings.open_data_button,
            self.settings.open_workspaces_button,
            self.sidebar_diagnostics_button,
            self.refresh_plan_button,
        ):
            self._configure_button(button, enabled=not busy)
        self._configure_button(
            self.settings.bind_profile_button,
            enabled=(
                not busy
                and bool(self.installation_key.get().strip())
            ),
        )
        self.settings.region_box.configure(state="disabled" if busy else "readonly")

        for tool_id, button in self.studio.tool_buttons.items():
            mutating = self.studio.tool_mutating.get(tool_id, True)
            self._configure_button(
                button,
                enabled=not busy and not (game_running and mutating),
                text=(
                    "Close game first"
                    if game_running and mutating
                    else "Open"
                ),
            )

    def show_page(self, key: str):
        if self._closing:
            return
        page = self.pages.get(key)
        if page is None:
            self.status.set(f"Unknown page: {key}")
            return
        page.tkraise()
        self.page_title.set(key.title())
        for name, button in self._nav_buttons.items():
            button.configure(
                style=(
                    "Active.Nav.TButton"
                    if name == key
                    else "Nav.TButton"
                )
            )
        if key == "conflicts":
            self.render_plan()
        self.refresh_action_states()

    @staticmethod
    def _set_text(widget: tk.Text, value: str):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="umml-manager")
    parser.add_argument(
        "--root",
        default="",
        help="override the Manager data directory",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=(
            "construct and render every page using disposable data, then exit; "
            "no real Manager or game files are touched"
        ),
    )
    return parser


def run_gui_smoke_test() -> None:
    """Render every page against disposable state and return without mainloop."""

    with tempfile.TemporaryDirectory(prefix="umml-manager-gui-smoke-") as temp:
        base = Path(temp)
        game = base / "game"
        dat = game / "UmamusumePrettyDerby_Data" / "Persistent" / "dat"
        meta = base / "meta.db"
        dat.mkdir(parents=True)
        meta.write_bytes(b"disposable-gui-smoke-metadata")
        store = ManagerStore(base / "manager")
        store.save_settings(
            {
                "dat_path": str(dat),
                "meta_path": str(meta),
                "game_dir": str(game),
                "region": "global",
                "installation_key": "gui-smoke",
                "metadata_fingerprint": hash_file(meta),
            }
        )

        root = tk.Tk()
        app = ManagerGUI(root, store)
        try:
            root.update_idletasks()
            root.update()
            for page in ("library", "discover", "studio", "conflicts", "settings"):
                app.show_page(page)
                root.update_idletasks()
                root.update()
            if set(app.pages) != {
                "library",
                "discover",
                "studio",
                "conflicts",
                "settings",
            }:
                raise RuntimeError("GUI smoke test did not construct every page")
        finally:
            app.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.smoke_test:
        run_gui_smoke_test()
        print(
            "GUI smoke test passed: every page rendered with disposable data; "
            "no real game files were changed"
        )
        return 0

    root = tk.Tk()
    store = ManagerStore(args.root) if args.root else None
    ManagerGUI(root, store)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

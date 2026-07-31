from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from .ui_support_bundle import create_support_bundle_from_ui
from .ui_theme import (
    THEME_SYSTEM,
    apply_widget_theme,
    configure_theme,
    normalize_theme_mode,
    resolve_theme_mode,
)

TESTING_GUIDE_URL = (
    "https://github.com/EvelynLimaB/Uma-Mod-Manager/blob/main/"
    "docs/TESTING_AND_FEEDBACK.md"
)
TESTING_FEEDBACK_URL = (
    "https://github.com/EvelynLimaB/Uma-Mod-Manager/issues/new?"
    "template=testing_feedback.yml"
)


class SettingsPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=1)
        saved_mode = normalize_theme_mode(
            app.store.load_settings().get("theme", THEME_SYSTEM)
        )
        self.theme_choice = tk.StringVar(value=saved_mode.title())
        self.theme_status = tk.StringVar()
        self._resolved_theme = ""

        appearance = ttk.LabelFrame(self, text="Appearance", padding=14)
        appearance.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        appearance.columnconfigure(0, weight=1)
        ttk.Label(
            appearance,
            text=(
                "Use the bright race-day palette, the darker evening palette, "
                "or follow the current KDE/GTK preference. Changes apply immediately."
            ),
            style="SurfaceMuted.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        controls = ttk.Frame(appearance, style="Surface.TFrame")
        controls.grid(row=0, column=1, rowspan=2, sticky="e", padx=(18, 0))
        ttk.Label(controls, text="Theme", style="Surface.TLabel").pack(side="left")
        self.theme_box = ttk.Combobox(
            controls,
            textvariable=self.theme_choice,
            values=("System", "Light", "Dark"),
            state="readonly",
            width=10,
        )
        self.theme_box.pack(side="left", padx=(8, 0))
        self.theme_box.bind("<<ComboboxSelected>>", self._theme_selected)
        ttk.Label(
            appearance,
            textvariable=self.theme_status,
            style="Surface.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(9, 0))

        start = ttk.LabelFrame(self, text="Installation setup", padding=14)
        start.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        start.columnconfigure(0, weight=1)
        ttk.Label(
            start,
            text=(
                "Uma Mod Manager normally finds Steam/Proton and prepares the "
                "metadata database for you. Manual paths are only needed for "
                "unusual installations."
            ),
            style="SurfaceMuted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        self.autodetect_button = ttk.Button(
            start,
            text="Auto-detect installation",
            style="Accent.TButton",
            command=app.autofill_installation,
        )
        self.autodetect_button.grid(row=0, column=1, sticky="e", padx=(16, 0))
        ttk.Label(
            start,
            textvariable=app.installation_status,
            style="Surface.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        paths = ttk.LabelFrame(self, text="Detected game and metadata paths", padding=14)
        paths.grid(row=2, column=0, sticky="ew")
        paths.columnconfigure(1, weight=1)
        self.dat_browse_button = self._row(
            paths,
            0,
            "Game asset data (Persistent/dat)",
            app.dat_path,
            app.choose_dat,
        )
        self.meta_browse_button = self._row(
            paths,
            1,
            "Prepared metadata database",
            app.meta_path,
            app.choose_meta,
        )
        self.game_browse_button = self._row(
            paths,
            2,
            "Game installation directory",
            app.game_dir,
            app.choose_game_dir,
        )
        region = ttk.Frame(paths, style="Surface.TFrame")
        region.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Label(region, text="Region", style="Surface.TLabel").pack(side="left")
        self.region_box = ttk.Combobox(
            region,
            textvariable=app.region,
            values=("global", "japan", "taiwan"),
            state="readonly",
            width=12,
        )
        self.region_box.pack(side="left", padx=8)
        ttk.Label(
            paths,
            text=(
                "The metadata field should point to UMML's readable "
                "meta_decrypted_*.db cache, not the game's encrypted file named meta."
            ),
            style="SurfaceMuted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))

        testing = ttk.LabelFrame(self, text="Community Test feedback", padding=14)
        testing.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        testing.columnconfigure(0, weight=1)
        ttk.Label(
            testing,
            text=(
                "Create a privacy-scrubbed report, inspect its JSON, then use the "
                "structured form for pass, partial, or failure results. Successful "
                "tests are evidence too."
            ),
            style="SurfaceMuted.TLabel",
            wraplength=670,
            justify="left",
        ).grid(row=0, column=0, sticky="w", padx=(0, 18))
        testing_controls = ttk.Frame(testing, style="Surface.TFrame")
        testing_controls.grid(row=0, column=1, sticky="e")
        testing_controls.columnconfigure((0, 1), weight=1)
        self.support_bundle_button = ttk.Button(
            testing_controls,
            text="Create support bundle",
            style="Accent.TButton",
            command=self._create_support_bundle,
        )
        self.support_bundle_button.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 6),
        )
        self.testing_guide_button = ttk.Button(
            testing_controls,
            text="Testing guide",
            command=self._open_testing_guide,
        )
        self.testing_guide_button.grid(row=1, column=0, sticky="ew", padx=(0, 3))
        self.testing_feedback_button = ttk.Button(
            testing_controls,
            text="Report feedback",
            command=self._open_testing_feedback,
        )
        self.testing_feedback_button.grid(row=1, column=1, sticky="ew", padx=(3, 0))

        actions = ttk.Frame(self, padding=(0, 12, 0, 0))
        actions.grid(row=4, column=0, sticky="ew")
        self.save_button = ttk.Button(
            actions,
            text="Save settings",
            style="Accent.TButton",
            command=app.save_settings,
        )
        self.save_button.pack(side="left")
        self.bind_profile_button = ttk.Button(
            actions,
            text="Bind profile here",
            command=app.rebind_profile,
        )
        self.bind_profile_button.pack(side="left", padx=8)
        self.diagnostics_button = ttk.Button(
            actions,
            text="Run diagnostics",
            command=app.run_diagnostics,
        )
        self.diagnostics_button.pack(side="left", padx=8)
        self.open_data_button = ttk.Button(
            actions,
            text="Open manager data",
            command=lambda: app.open_manager_path("root"),
        )
        self.open_data_button.pack(side="right")
        self.open_workspaces_button = ttk.Button(
            actions,
            text="Open workspaces",
            command=lambda: app.open_manager_path("workspaces"),
        )
        self.open_workspaces_button.pack(side="right", padx=8)

        self._apply_theme(persist=False)
        app.root.bind_all("<Map>", self._theme_mapped_widget, add="+")
        self._schedule_system_refresh()

    def _create_support_bundle(self) -> None:
        create_support_bundle_from_ui(self.app)

    def _open_testing_guide(self) -> None:
        self._open_web(TESTING_GUIDE_URL, "testing guide")

    def _open_testing_feedback(self) -> None:
        self._open_web(TESTING_FEEDBACK_URL, "testing feedback form")

    def _open_web(self, url: str, label: str) -> None:
        try:
            opened = webbrowser.open(url, new=2)
        except Exception as exc:
            messagebox.showerror(
                f"Could not open {label}",
                str(exc),
                parent=self.app.root,
            )
            return
        if not opened:
            messagebox.showerror(
                f"Could not open {label}",
                (
                    "No web browser accepted the link. Open it from the repository "
                    "documentation instead."
                ),
                parent=self.app.root,
            )
            return
        self.app.status.set(f"Opened {label}")

    def _theme_selected(self, _event=None) -> None:
        self._apply_theme(persist=True)

    def _apply_theme(self, *, persist: bool) -> None:
        requested = normalize_theme_mode(self.theme_choice.get())
        palette = configure_theme(self.app.root, requested)
        self.app.theme_palette = palette
        self._resolved_theme = palette.name
        if requested == THEME_SYSTEM:
            self.theme_status.set(
                f"Following the desktop preference. Currently using {palette.name.title()}."
            )
        else:
            self.theme_status.set(f"Using the {palette.name.title()} palette.")
        if persist:
            try:
                self.app.store.save_settings({"theme": requested})
            except Exception as exc:
                self.app.status.set(f"Theme changed, but could not be saved: {exc}")
            else:
                self.app.status.set(f"Theme changed to {self.theme_choice.get()}")

    def _theme_mapped_widget(self, event) -> None:
        palette = getattr(self.app, "theme_palette", None)
        if palette is None or getattr(self.app, "_closing", False):
            return
        apply_widget_theme(event.widget, palette)

    def _schedule_system_refresh(self) -> None:
        if getattr(self.app, "_closing", False):
            return
        if normalize_theme_mode(self.theme_choice.get()) == THEME_SYSTEM:
            resolved = resolve_theme_mode(THEME_SYSTEM)
            if resolved != self._resolved_theme:
                self._apply_theme(persist=False)
        try:
            self.app.root.after(5000, self._schedule_system_refresh)
        except tk.TclError:
            return

    @staticmethod
    def _row(parent, row, label, variable, command):
        ttk.Label(parent, text=label, style="Surface.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky="ew", pady=4
        )
        button = ttk.Button(parent, text="Browse", command=command)
        button.grid(row=row, column=2, padx=(8, 0), pady=4)
        return button

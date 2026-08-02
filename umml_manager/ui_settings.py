from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from .ui_scrollable import ScrollablePage
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


class SettingsPage(ScrollablePage):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        page = self.content
        page.columnconfigure(0, weight=1)

        saved_mode = normalize_theme_mode(
            app.store.load_settings().get("theme", THEME_SYSTEM)
        )
        self.theme_choice = tk.StringVar(value=saved_mode.title())
        self.theme_status = tk.StringVar()
        self._resolved_theme = ""
        self._path_rows: list[tuple[ttk.Frame, ttk.Label, ttk.Entry, ttk.Button]] = []

        self.appearance = ttk.LabelFrame(page, text="Appearance", padding=14)
        self.appearance.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.appearance.columnconfigure(0, weight=1)
        self.appearance_description = ttk.Label(
            self.appearance,
            text=(
                "Use the bright race-day palette, the darker evening palette, "
                "or follow the current KDE/GTK preference. Changes apply immediately."
            ),
            style="SurfaceMuted.TLabel",
            justify="left",
        )
        self.appearance_controls = ttk.Frame(
            self.appearance,
            style="Surface.TFrame",
        )
        ttk.Label(
            self.appearance_controls,
            text="Theme",
            style="Surface.TLabel",
        ).pack(side="left")
        self.theme_box = ttk.Combobox(
            self.appearance_controls,
            textvariable=self.theme_choice,
            values=("System", "Light", "Dark"),
            state="readonly",
            width=10,
        )
        self.theme_box.pack(side="left", padx=(8, 0))
        self.theme_box.bind("<<ComboboxSelected>>", self._theme_selected)
        self.theme_status_label = ttk.Label(
            self.appearance,
            textvariable=self.theme_status,
            style="Surface.TLabel",
            justify="left",
        )

        self.installation = ttk.LabelFrame(
            page,
            text="Installation setup",
            padding=14,
        )
        self.installation.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.installation.columnconfigure(0, weight=1)
        self.installation_description = ttk.Label(
            self.installation,
            text=(
                "Uma Mod Manager normally finds Steam/Proton and prepares the "
                "metadata database for you. Manual paths are only needed for "
                "unusual installations."
            ),
            style="SurfaceMuted.TLabel",
            justify="left",
        )
        self.autodetect_button = ttk.Button(
            self.installation,
            text="Auto-detect installation",
            style="Accent.TButton",
            command=app.autofill_installation,
        )
        self.installation_status_label = ttk.Label(
            self.installation,
            textvariable=app.installation_status,
            style="Surface.TLabel",
            justify="left",
        )

        self.paths = ttk.LabelFrame(
            page,
            text="Detected game and metadata paths",
            padding=14,
        )
        self.paths.grid(row=2, column=0, sticky="ew")
        self.paths.columnconfigure(0, weight=1)
        self.dat_browse_button = self._path_row(
            self.paths,
            0,
            "Game asset data (Persistent/dat)",
            app.dat_path,
            app.choose_dat,
        )
        self.meta_browse_button = self._path_row(
            self.paths,
            1,
            "Prepared metadata database",
            app.meta_path,
            app.choose_meta,
        )
        self.game_browse_button = self._path_row(
            self.paths,
            2,
            "Game installation directory",
            app.game_dir,
            app.choose_game_dir,
        )
        self.region_frame = ttk.Frame(self.paths, style="Surface.TFrame")
        self.region_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(
            self.region_frame,
            text="Region",
            style="Surface.TLabel",
        ).pack(side="left")
        self.region_box = ttk.Combobox(
            self.region_frame,
            textvariable=app.region,
            values=("global", "japan", "taiwan"),
            state="readonly",
            width=12,
        )
        self.region_box.pack(side="left", padx=8)
        self.paths_note = ttk.Label(
            self.paths,
            text=(
                "The metadata field should point to UMML's readable "
                "meta_decrypted_*.db cache, not the game's encrypted file named meta."
            ),
            style="SurfaceMuted.TLabel",
            justify="left",
        )
        self.paths_note.grid(row=4, column=0, sticky="w", pady=(10, 0))

        self.testing = ttk.LabelFrame(
            page,
            text="Community Test feedback",
            padding=14,
        )
        self.testing.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.testing.columnconfigure(0, weight=1)
        self.testing_description = ttk.Label(
            self.testing,
            text=(
                "Create a privacy-scrubbed report, inspect its JSON, then use the "
                "structured form for pass, partial, or failure results. Successful "
                "tests are evidence too."
            ),
            style="SurfaceMuted.TLabel",
            justify="left",
        )
        self.testing_controls = ttk.Frame(
            self.testing,
            style="Surface.TFrame",
        )
        self.testing_controls.columnconfigure(0, weight=1)
        self.testing_controls.columnconfigure(1, weight=1)
        self.support_bundle_button = ttk.Button(
            self.testing_controls,
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
            self.testing_controls,
            text="Testing guide",
            command=self._open_testing_guide,
        )
        self.testing_guide_button.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=(0, 3),
        )
        self.testing_feedback_button = ttk.Button(
            self.testing_controls,
            text="Report feedback",
            command=self._open_testing_feedback,
        )
        self.testing_feedback_button.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(3, 0),
        )

        self.actions = ttk.Frame(page, padding=(0, 12, 0, 8))
        self.actions.grid(row=4, column=0, sticky="ew")
        self.save_button = ttk.Button(
            self.actions,
            text="Save settings",
            style="Accent.TButton",
            command=app.save_settings,
        )
        self.bind_profile_button = ttk.Button(
            self.actions,
            text="Bind profile here",
            command=app.rebind_profile,
        )
        self.diagnostics_button = ttk.Button(
            self.actions,
            text="Run diagnostics",
            command=app.run_diagnostics,
        )
        self.open_data_button = ttk.Button(
            self.actions,
            text="Open manager data",
            command=lambda: app.open_manager_path("root"),
        )
        self.open_workspaces_button = ttk.Button(
            self.actions,
            text="Open workspaces",
            command=lambda: app.open_manager_path("workspaces"),
        )
        self._action_buttons = (
            self.save_button,
            self.bind_profile_button,
            self.diagnostics_button,
            self.open_workspaces_button,
            self.open_data_button,
        )

        self.set_resize_callback(self._reflow)
        self.finalize_scroll_bindings()
        self._apply_theme(persist=False)
        app.root.bind_all("<Map>", self._theme_mapped_widget, add="+")
        self._schedule_system_refresh()

    def _path_row(self, parent, row, label, variable, command):
        frame = ttk.Frame(parent, style="Surface.TFrame")
        frame.grid(row=row, column=0, sticky="ew", pady=4)
        frame.columnconfigure(1, weight=1)
        label_widget = ttk.Label(
            frame,
            text=label,
            style="Surface.TLabel",
            justify="left",
        )
        entry = ttk.Entry(frame, textvariable=variable)
        button = ttk.Button(frame, text="Browse", command=command)
        self._path_rows.append((frame, label_widget, entry, button))
        return button

    def _reflow(self, width: int) -> None:
        compact = width < 860
        text_width = max(260, width - (62 if compact else 330))
        full_width = max(260, width - 48)

        for widget in (
            self.appearance_description,
            self.appearance_controls,
            self.theme_status_label,
        ):
            widget.grid_forget()
        if compact:
            self.appearance_description.grid(row=0, column=0, sticky="w")
            self.appearance_controls.grid(
                row=1,
                column=0,
                sticky="w",
                pady=(10, 0),
            )
            self.theme_status_label.grid(
                row=2,
                column=0,
                sticky="w",
                pady=(9, 0),
            )
        else:
            self.appearance_description.grid(row=0, column=0, sticky="w")
            self.appearance_controls.grid(
                row=0,
                column=1,
                rowspan=2,
                sticky="e",
                padx=(18, 0),
            )
            self.theme_status_label.grid(
                row=1,
                column=0,
                sticky="w",
                pady=(9, 0),
            )
        self.appearance_description.configure(wraplength=text_width)
        self.theme_status_label.configure(wraplength=full_width)

        for widget in (
            self.installation_description,
            self.autodetect_button,
            self.installation_status_label,
        ):
            widget.grid_forget()
        if compact:
            self.installation_description.grid(row=0, column=0, sticky="w")
            self.autodetect_button.grid(
                row=1,
                column=0,
                sticky="w",
                pady=(10, 0),
            )
            self.installation_status_label.grid(
                row=2,
                column=0,
                sticky="w",
                pady=(10, 0),
            )
        else:
            self.installation_description.grid(row=0, column=0, sticky="w")
            self.autodetect_button.grid(
                row=0,
                column=1,
                sticky="e",
                padx=(16, 0),
            )
            self.installation_status_label.grid(
                row=1,
                column=0,
                columnspan=2,
                sticky="w",
                pady=(10, 0),
            )
        self.installation_description.configure(wraplength=text_width)
        self.installation_status_label.configure(wraplength=full_width)

        for frame, label, entry, button in self._path_rows:
            label.grid_forget()
            entry.grid_forget()
            button.grid_forget()
            frame.columnconfigure(0, weight=0)
            frame.columnconfigure(1, weight=0)
            frame.columnconfigure(2, weight=0)
            if compact:
                frame.columnconfigure(0, weight=1)
                label.grid(
                    row=0,
                    column=0,
                    columnspan=2,
                    sticky="w",
                    pady=(0, 4),
                )
                entry.grid(row=1, column=0, sticky="ew")
                button.grid(row=1, column=1, padx=(8, 0))
                label.configure(wraplength=full_width)
            else:
                frame.columnconfigure(1, weight=1)
                label.grid(row=0, column=0, sticky="w", padx=(0, 8))
                entry.grid(row=0, column=1, sticky="ew")
                button.grid(row=0, column=2, padx=(8, 0))
                label.configure(wraplength=260)
        self.paths_note.configure(wraplength=full_width)

        for widget in (self.testing_description, self.testing_controls):
            widget.grid_forget()
        if compact:
            self.testing_description.grid(row=0, column=0, sticky="w")
            self.testing_controls.grid(
                row=1,
                column=0,
                sticky="ew",
                pady=(12, 0),
            )
        else:
            self.testing_description.grid(
                row=0,
                column=0,
                sticky="w",
                padx=(0, 18),
            )
            self.testing_controls.grid(row=0, column=1, sticky="e")
        self.testing_description.configure(wraplength=text_width)

        for button in self._action_buttons:
            button.grid_forget()
        for column in range(6):
            self.actions.columnconfigure(column, weight=0)
        if compact:
            self.actions.columnconfigure(0, weight=1)
            self.actions.columnconfigure(1, weight=1)
            self.save_button.grid(
                row=0,
                column=0,
                columnspan=2,
                sticky="ew",
                pady=(0, 6),
            )
            self.bind_profile_button.grid(
                row=1,
                column=0,
                sticky="ew",
                padx=(0, 3),
                pady=3,
            )
            self.diagnostics_button.grid(
                row=1,
                column=1,
                sticky="ew",
                padx=(3, 0),
                pady=3,
            )
            self.open_workspaces_button.grid(
                row=2,
                column=0,
                sticky="ew",
                padx=(0, 3),
                pady=3,
            )
            self.open_data_button.grid(
                row=2,
                column=1,
                sticky="ew",
                padx=(3, 0),
                pady=3,
            )
        else:
            self.actions.columnconfigure(3, weight=1)
            self.save_button.grid(row=0, column=0, sticky="w")
            self.bind_profile_button.grid(
                row=0,
                column=1,
                sticky="w",
                padx=(8, 0),
            )
            self.diagnostics_button.grid(
                row=0,
                column=2,
                sticky="w",
                padx=(8, 0),
            )
            self.open_workspaces_button.grid(
                row=0,
                column=4,
                sticky="e",
                padx=(8, 0),
            )
            self.open_data_button.grid(
                row=0,
                column=5,
                sticky="e",
                padx=(8, 0),
            )

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

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .options import OptionError, normalize_profile_options, option_summary
from .ui_mod_options import configure_mod_options
from .ui_package_builder import launch_package_builder
from .ui_theme import SURFACE_2, TEXT


class LibraryPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(0, 0, 0, 10))
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        ttk.Label(toolbar, text="Profile").grid(row=0, column=0, padx=(0, 7))
        self.profile_box = ttk.Combobox(
            toolbar,
            textvariable=app.profile_name,
            state="readonly",
            width=22,
        )
        self.profile_box.grid(row=0, column=1, sticky="w")

        def profile_selected(_event):
            app.refresh()
            app.save_settings(silent=True)
            self.refresh_option_state()

        self.profile_box.bind("<<ComboboxSelected>>", profile_selected)
        self.new_profile_button = ttk.Button(
            toolbar, text="New profile", command=app.new_profile
        )
        self.new_profile_button.grid(row=0, column=2, padx=4)
        self.search_entry = ttk.Entry(
            toolbar, textvariable=app.search_library, width=26
        )
        self.search_entry.grid(row=0, column=3, padx=(14, 4))
        self.search_entry.bind("<Return>", lambda _event: app.refresh())
        self.search_button = ttk.Button(toolbar, text="Search", command=app.refresh)
        self.search_button.grid(row=0, column=4)
        self.new_package_button = ttk.Button(
            toolbar,
            text="New package",
            command=lambda: launch_package_builder(app),
        )
        self.new_package_button.grid(row=0, column=5, padx=(14, 4))
        self.import_folder_button = ttk.Button(
            toolbar, text="Import folder", command=app.import_folder
        )
        self.import_folder_button.grid(row=0, column=6, padx=4)
        self.import_archive_button = ttk.Button(
            toolbar, text="Import archive", command=app.import_archive
        )
        self.import_archive_button.grid(row=0, column=7, padx=4)

        left = ttk.Frame(self, style="Surface.TFrame", padding=10)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 7))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            left,
            columns=("order", "version", "source", "state"),
            show="tree headings",
            selectmode="browse",
        )
        for column, title, width in (
            ("#0", "Mod", 280),
            ("order", "Order", 70),
            ("version", "Version", 90),
            ("source", "Source", 100),
            ("state", "State", 160),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(
                column,
                width=width,
                anchor="center" if column != "#0" else "w",
            )
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._selected_changed)
        self.tree.bind("<Double-1>", lambda _event: app.toggle_mod())

        details = ttk.Frame(self, style="Surface.TFrame", padding=16)
        details.grid(row=1, column=1, sticky="nsew", padx=(7, 0))
        details.columnconfigure(0, weight=1)
        details.rowconfigure(4, weight=1)
        self.mod_title = ttk.Label(
            details, text="Select a mod", style="CardTitle.TLabel"
        )
        self.mod_title.grid(row=0, column=0, sticky="w")
        self.mod_meta = ttk.Label(details, text="", style="SurfaceMuted.TLabel")
        self.mod_meta.grid(row=1, column=0, sticky="w", pady=(3, 10))
        self.mod_state = ttk.Label(details, text="", style="Badge.TLabel")
        self.mod_state.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.option_state = ttk.Label(
            details,
            text="",
            style="SurfaceMuted.TLabel",
            wraplength=430,
            justify="left",
        )
        self.option_state.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.description = tk.Text(
            details,
            wrap="word",
            height=12,
            background=SURFACE_2,
            foreground=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
        )
        self.description.grid(row=4, column=0, sticky="nsew")
        self.description.configure(state="disabled")
        buttons = ttk.Frame(details, style="Surface.TFrame")
        buttons.grid(row=5, column=0, sticky="ew", pady=(12, 0))
        self.toggle_button = ttk.Button(
            buttons, text="Enable", command=app.toggle_mod, state="disabled"
        )
        self.toggle_button.pack(side="left")
        self.move_up_button = ttk.Button(
            buttons,
            text="↑",
            width=3,
            command=lambda: app.move_mod(-1),
            state="disabled",
        )
        self.move_up_button.pack(side="left", padx=(6, 2))
        self.move_down_button = ttk.Button(
            buttons,
            text="↓",
            width=3,
            command=lambda: app.move_mod(1),
            state="disabled",
        )
        self.move_down_button.pack(side="left", padx=2)
        self.configure_button = ttk.Button(
            buttons,
            text="Configure",
            command=lambda: configure_mod_options(app, self),
            state="disabled",
        )
        self.configure_button.pack(side="left", padx=(8, 2))
        self.prepare_button = ttk.Button(
            buttons,
            text="Prepare",
            command=app.prepare_selected,
            state="disabled",
        )
        self.prepare_button.pack(side="left", padx=2)
        self.workspace_button = ttk.Button(
            buttons,
            text="Edit copy",
            command=app.create_workspace,
            state="disabled",
        )
        self.workspace_button.pack(side="left", padx=2)
        self.remove_button = ttk.Button(
            buttons,
            text="Remove",
            style="Danger.TButton",
            command=app.remove_selected,
            state="disabled",
        )
        self.remove_button.pack(side="right")

        actions = ttk.Frame(self, padding=(0, 10, 0, 0))
        actions.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.preview_conflicts_button = ttk.Button(
            actions, text="Preview conflicts", command=app.show_plan
        )
        self.preview_conflicts_button.pack(side="left")
        self.apply_button = ttk.Button(
            actions,
            text="Apply profile",
            style="Accent.TButton",
            command=app.apply_profile,
        )
        self.apply_button.pack(side="right")

    def _selected_changed(self, _event=None) -> None:
        self.app.show_selected_mod()
        self.refresh_option_state()

    def selected_id(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def clear_details(self) -> None:
        self.mod_title.configure(text="Select a mod")
        self.mod_meta.configure(text="")
        self.mod_state.configure(text="")
        self.option_state.configure(text="")
        self.configure_button.configure(state="disabled")
        self.set_description("")

    def set_description(self, value: str) -> None:
        self.description.configure(state="normal")
        self.description.delete("1.0", "end")
        self.description.insert("1.0", value)
        self.description.configure(state="disabled")
        self.after_idle(self.refresh_option_state)

    def refresh_option_state(self, *, record=None, profile=None) -> None:
        mod_id = self.selected_id()
        if not mod_id:
            self.option_state.configure(text="")
            self.configure_button.configure(state="disabled")
            return
        try:
            record = record or self.app.store.get_mod(mod_id)
            if not record.option_groups:
                self.option_state.configure(text="")
                self.configure_button.configure(state="disabled")
                return
            profile = profile or self.app.profile()
            selections = normalize_profile_options(
                record.option_groups,
                profile.options.get(mod_id, {}),
            )
            summary = option_summary(record.option_groups, selections)
            if record.files and not record.source_files:
                summary += " • Re-prepare required for option mapping"
            self.option_state.configure(text="Profile options • " + summary)
            self.configure_button.configure(
                state="disabled" if getattr(self.app, "_busy", False) else "normal"
            )
        except OptionError as exc:
            self.option_state.configure(text=f"Invalid profile options: {exc}")
            self.configure_button.configure(state="normal")
        except Exception as exc:
            self.option_state.configure(text=f"Could not load options: {exc}")
            self.configure_button.configure(state="disabled")

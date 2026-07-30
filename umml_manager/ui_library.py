from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .mod_inspection import inspect_mod
from .options import OptionError, normalize_profile_options, option_summary
from .ui_mod_inspector import inspect_selected_mod
from .ui_mod_options import configure_mod_options
from .ui_package_builder import launch_package_builder
from .ui_theme import SURFACE_2, TEXT


class _HiddenAction:
    """Compatibility shim for actions intentionally removed from the visible UI."""

    def configure(self, **_kwargs) -> None:
        return None


class LibraryPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=(0, 0, 0, 10))
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.columnconfigure(3, weight=1)
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
            toolbar,
            text="New profile",
            command=app.new_profile,
        )
        self.new_profile_button.grid(row=0, column=2, padx=(6, 14))

        self.search_entry = ttk.Entry(toolbar, textvariable=app.search_library)
        self.search_entry.grid(row=0, column=3, sticky="ew", padx=(0, 6))
        self.search_entry.bind("<Return>", lambda _event: app.refresh())
        self.search_button = ttk.Button(toolbar, text="Search", command=app.refresh)
        self.search_button.grid(row=0, column=4, padx=(0, 14))

        self.new_package_button = ttk.Button(
            toolbar,
            text="New package",
            command=lambda: launch_package_builder(app),
        )
        self.new_package_button.grid(row=0, column=5, padx=(0, 6))
        self.import_folder_button = ttk.Button(
            toolbar,
            text="Import folder",
            command=app.import_folder,
        )
        self.import_folder_button.grid(row=0, column=6, padx=3)
        self.import_archive_button = ttk.Button(
            toolbar,
            text="Import archive",
            command=app.import_archive,
        )
        self.import_archive_button.grid(row=0, column=7, padx=(3, 0))

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
            ("#0", "Mod", 300),
            ("order", "Order", 72),
            ("version", "Version", 100),
            ("source", "Source", 105),
            ("state", "State", 170),
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
        details.rowconfigure(5, weight=1)
        self.mod_title = ttk.Label(details, text="Select a mod", style="CardTitle.TLabel")
        self.mod_title.grid(row=0, column=0, sticky="w")
        self.mod_meta = ttk.Label(details, text="", style="SurfaceMuted.TLabel")
        self.mod_meta.grid(row=1, column=0, sticky="w", pady=(3, 10))
        self.mod_state = ttk.Label(details, text="", style="Badge.TLabel")
        self.mod_state.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self.inspection_state = ttk.Label(
            details,
            text="",
            style="SurfaceMuted.TLabel",
            wraplength=520,
            justify="left",
        )
        self.inspection_state.grid(row=3, column=0, sticky="ew", pady=(0, 5))
        self.option_state = ttk.Label(
            details,
            text="",
            style="SurfaceMuted.TLabel",
            wraplength=520,
            justify="left",
        )
        self.option_state.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.description = tk.Text(
            details,
            wrap="word",
            height=11,
            background=SURFACE_2,
            foreground=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
        )
        self.description.grid(row=5, column=0, sticky="nsew")
        self.description.configure(state="disabled")

        profile_buttons = ttk.Frame(details, style="Surface.TFrame")
        profile_buttons.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        for column in range(4):
            profile_buttons.columnconfigure(column, weight=1)
        self.toggle_button = ttk.Button(
            profile_buttons,
            text="Enable",
            command=app.toggle_mod,
            state="disabled",
        )
        self.toggle_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.move_up_button = ttk.Button(
            profile_buttons,
            text="Move up",
            command=lambda: app.move_mod(-1),
            state="disabled",
        )
        self.move_up_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.move_down_button = ttk.Button(
            profile_buttons,
            text="Move down",
            command=lambda: app.move_mod(1),
            state="disabled",
        )
        self.move_down_button.grid(row=0, column=2, sticky="ew", padx=4)
        self.configure_button = ttk.Button(
            profile_buttons,
            text="Configure profile",
            command=lambda: configure_mod_options(app, self),
            state="disabled",
        )
        self.configure_button.grid(row=0, column=3, sticky="ew", padx=(4, 0))
        self.prepare_button = _HiddenAction()

        source_buttons = ttk.Frame(details, style="Surface.TFrame")
        source_buttons.grid(row=7, column=0, sticky="ew", pady=(8, 0))
        source_buttons.columnconfigure(0, weight=2)
        source_buttons.columnconfigure(1, weight=1)
        source_buttons.columnconfigure(2, weight=1)
        self.edit_package_button = ttk.Button(
            source_buttons,
            text="Inspect & edit",
            style="Accent.TButton",
            command=lambda: inspect_selected_mod(app, self),
            state="disabled",
        )
        self.edit_package_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.workspace_button = ttk.Button(
            source_buttons,
            text="Open files externally",
            command=app.create_workspace,
            state="disabled",
        )
        self.workspace_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.remove_button = ttk.Button(
            source_buttons,
            text="Remove",
            style="Danger.TButton",
            command=app.remove_selected,
            state="disabled",
        )
        self.remove_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        actions = ttk.Frame(self, padding=(0, 10, 0, 0))
        actions.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.preview_conflicts_button = ttk.Button(
            actions,
            text="Preview profile plan",
            command=app.show_plan,
        )
        self.preview_conflicts_button.pack(side="left")
        self.apply_button = ttk.Button(
            actions,
            text="Apply profile",
            style="Accent.TButton",
            command=app.apply_profile,
        )
        self.apply_button.pack(side="right")

        self.set_description(
            "Select a mod to inspect what it changes, edit compatibility metadata, "
            "or create simple per-profile component controls. Preparation and refreshes are automatic."
        )

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
        self.inspection_state.configure(text="")
        self.option_state.configure(text="")
        self.configure_button.configure(state="disabled")
        self.edit_package_button.configure(state="disabled")
        self.set_description(
            "Select a mod to inspect what it changes, edit compatibility metadata, "
            "or create simple per-profile component controls. Preparation and refreshes are automatic."
        )

    def set_description(self, value: str) -> None:
        self.description.configure(state="normal")
        self.description.delete("1.0", "end")
        self.description.insert("1.0", value)
        self.description.configure(state="disabled")
        self.after_idle(self.refresh_option_state)

    def refresh_option_state(self, *, record=None, profile=None) -> None:
        mod_id = self.selected_id()
        if not mod_id:
            self.inspection_state.configure(text="")
            self.option_state.configure(text="")
            self.configure_button.configure(state="disabled")
            self.edit_package_button.configure(state="disabled")
            return
        try:
            record = record or self.app.store.get_mod(mod_id)
            busy = bool(getattr(self.app, "_busy", False))
            inspection = inspect_mod(record)
            inspection_text = "Detected changes • " + inspection.summary()
            if inspection.warnings:
                inspection_text += "\n" + inspection.warnings[0]
            self.inspection_state.configure(text=inspection_text)
            self.edit_package_button.configure(state="disabled" if busy else "normal")

            if not record.option_groups:
                self.option_state.configure(
                    text=(
                        "No profile controls yet. Inspect & edit can turn mapped source bundles into "
                        "component checkboxes or mutually exclusive variants."
                    )
                )
                self.configure_button.configure(state="disabled")
                return

            profile = profile or self.app.profile()
            selections = normalize_profile_options(
                record.option_groups,
                profile.options.get(mod_id, {}),
            )
            summary = option_summary(record.option_groups, selections)
            if not record.source_payloads:
                summary += " • automatic source indexing queued"
            self.option_state.configure(text="Profile options • " + summary)
            self.configure_button.configure(state="disabled" if busy else "normal")
        except OptionError as exc:
            self.option_state.configure(text=f"Invalid profile options: {exc}")
            self.configure_button.configure(state="normal")
        except Exception as exc:
            self.inspection_state.configure(text=f"Could not inspect assets: {exc}")
            self.option_state.configure(text=f"Could not load options: {exc}")
            self.configure_button.configure(state="disabled")
            self.edit_package_button.configure(state="normal")

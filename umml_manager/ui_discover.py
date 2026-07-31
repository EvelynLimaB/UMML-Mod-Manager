from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .ui_theme import SURFACE_2, TEXT


class DiscoverPage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._gb_preview_photo: ImageTk.PhotoImage | None = None
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.gb = ttk.Frame(notebook, padding=12)
        self.local = ttk.Frame(notebook, padding=12)
        notebook.add(self.gb, text="GameBanana")
        notebook.add(self.local, text="Local folders")
        self._build_gamebanana()
        self._build_local()

    def _build_gamebanana(self):
        page = self.gb
        page.columnconfigure(0, weight=3)
        page.columnconfigure(1, weight=2)
        page.rowconfigure(1, weight=1)
        bar = ttk.Frame(page)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(bar, text="Game").pack(side="left")
        self.gb_region_box = ttk.Combobox(
            bar,
            textvariable=self.app.gb_region,
            values=("global", "japan"),
            state="readonly",
            width=10,
        )
        self.gb_region_box.pack(side="left", padx=(6, 12))
        ttk.Label(bar, text="Sort").pack(side="left")
        self.gb_sort_box = ttk.Combobox(
            bar,
            textvariable=self.app.gb_sort,
            values=("updated", "newest", "popular", "downloads", "views"),
            state="readonly",
            width=11,
        )
        self.gb_sort_box.pack(side="left", padx=(6, 12))
        self.gb_query_entry = ttk.Entry(bar, textvariable=self.app.gb_query, width=30)
        self.gb_query_entry.pack(side="left", fill="x", expand=True)
        self.gb_query_entry.bind("<Return>", lambda _event: self.app.browse_gamebanana())
        self.browse_button = ttk.Button(
            bar,
            text="Browse",
            style="Accent.TButton",
            command=self.app.browse_gamebanana,
        )
        self.browse_button.pack(side="left", padx=(8, 0))

        left = ttk.Frame(page, style="Surface.TFrame", padding=10)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 7))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.gb_tree = ttk.Treeview(
            left,
            columns=("author", "version", "downloads"),
            show="tree headings",
        )
        for col, title, width in (
            ("#0", "Mod", 280),
            ("author", "Author", 130),
            ("version", "Version", 80),
            ("downloads", "Downloads", 90),
        ):
            self.gb_tree.heading(col, text=title)
            self.gb_tree.column(
                col, width=width, anchor="center" if col != "#0" else "w"
            )
        gb_scroll = ttk.Scrollbar(left, orient="vertical", command=self.gb_tree.yview)
        self.gb_tree.configure(yscrollcommand=gb_scroll.set)
        self.gb_tree.grid(row=0, column=0, sticky="nsew")
        gb_scroll.grid(row=0, column=1, sticky="ns")
        self.gb_tree.bind(
            "<<TreeviewSelect>>", lambda _e: self.app.select_gamebanana_mod()
        )

        right = ttk.Frame(page, style="Surface.TFrame", padding=16)
        right.grid(row=1, column=1, sticky="nsew", padx=(7, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(5, weight=1)
        self.gb_title = ttk.Label(
            right, text="Browse Umamusume mods", style="CardTitle.TLabel"
        )
        self.gb_title.grid(row=0, column=0, sticky="w")
        self.gb_meta = ttk.Label(
            right,
            text="Global and Japan are separate GameBanana games.",
            style="SurfaceMuted.TLabel",
            wraplength=400,
        )
        self.gb_meta.grid(row=1, column=0, sticky="w", pady=(3, 8))
        self.gb_stats = ttk.Label(right, text="", style="Badge.TLabel")
        self.gb_stats.grid(row=2, column=0, sticky="w", pady=(0, 8))

        self.gb_preview_frame = tk.Frame(
            right,
            background=SURFACE_2,
            height=210,
            highlightthickness=0,
            borderwidth=0,
        )
        self.gb_preview_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.gb_preview_frame.grid_propagate(False)
        self.gb_preview_frame.columnconfigure(0, weight=1)
        self.gb_preview_frame.rowconfigure(0, weight=1)
        self.gb_preview = tk.Label(
            self.gb_preview_frame,
            text="Select a mod to load its preview.",
            background=SURFACE_2,
            foreground=TEXT,
            compound="center",
            anchor="center",
            justify="center",
            padx=10,
            pady=10,
        )
        self.gb_preview.grid(row=0, column=0, sticky="nsew")
        self.gb_preview_source = ttk.Label(
            right,
            text="",
            style="SurfaceMuted.TLabel",
            anchor="e",
        )
        self.gb_preview_source.grid(row=4, column=0, sticky="ew", pady=(0, 6))

        self.gb_description = tk.Text(
            right,
            wrap="word",
            background=SURFACE_2,
            foreground=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
        )
        self.gb_description.grid(row=5, column=0, sticky="nsew")
        self.gb_description.configure(state="disabled")
        self.gb_files = ttk.Combobox(right, state="readonly")
        self.gb_files.grid(row=6, column=0, sticky="ew", pady=(10, 5))
        buttons = ttk.Frame(right, style="Surface.TFrame")
        buttons.grid(row=7, column=0, sticky="ew")
        self.open_gb_button = ttk.Button(
            buttons,
            text="Open page",
            command=self.app.open_gamebanana_page,
            state="disabled",
        )
        self.open_gb_button.pack(side="left")
        self.install_gb_button = ttk.Button(
            buttons,
            text="Install",
            style="Accent.TButton",
            command=self.app.install_gamebanana_mod,
            state="disabled",
        )
        self.install_gb_button.pack(side="right")

        pager = ttk.Frame(page)
        pager.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.prev_button = ttk.Button(
            pager,
            text="← Previous",
            command=lambda: self.app.change_gamebanana_page(-1),
            state="disabled",
        )
        self.prev_button.pack(side="left")
        self.page_label = ttk.Label(pager, text="Page 1")
        self.page_label.pack(side="left", padx=12)
        self.next_button = ttk.Button(
            pager,
            text="Next →",
            command=lambda: self.app.change_gamebanana_page(1),
            state="disabled",
        )
        self.next_button.pack(side="left")

    def _build_local(self):
        page = self.local
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        bar = ttk.Frame(page)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(bar, text="Search roots").pack(side="left")
        self.scan_roots_entry = ttk.Entry(bar, textvariable=self.app.scan_roots)
        self.scan_roots_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.scan_roots_entry.bind("<Return>", lambda _event: self.app.scan_local_mods())
        self.add_folder_button = ttk.Button(
            bar,
            text="Add folder",
            command=self.app.add_scan_root,
        )
        self.add_folder_button.pack(side="left", padx=4)
        self.scan_button = ttk.Button(
            bar,
            text="Scan",
            style="Accent.TButton",
            command=self.app.scan_local_mods,
        )
        self.scan_button.pack(side="left")
        frame = ttk.Frame(page, style="Surface.TFrame", padding=10)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.local_tree = ttk.Treeview(
            frame,
            columns=("kind", "confidence", "reason", "path"),
            show="tree headings",
        )
        for col, title, width in (
            ("#0", "Candidate", 220),
            ("kind", "Type", 80),
            ("confidence", "Confidence", 90),
            ("reason", "Detected by", 180),
            ("path", "Path", 400),
        ):
            self.local_tree.heading(col, text=title)
            self.local_tree.column(
                col,
                width=width,
                anchor="center" if col in {"kind", "confidence"} else "w",
            )
        local_scroll = ttk.Scrollbar(
            frame, orient="vertical", command=self.local_tree.yview
        )
        self.local_tree.configure(yscrollcommand=local_scroll.set)
        self.local_tree.grid(row=0, column=0, sticky="nsew")
        local_scroll.grid(row=0, column=1, sticky="ns")
        self.local_tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self.app.refresh_action_states(),
        )
        buttons = ttk.Frame(page)
        buttons.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.open_local_button = ttk.Button(
            buttons,
            text="Open location",
            command=self.app.open_local_candidate,
            state="disabled",
        )
        self.open_local_button.pack(side="left")
        self.import_local_button = ttk.Button(
            buttons,
            text="Import selected",
            style="Accent.TButton",
            command=self.app.import_local_candidate,
            state="disabled",
        )
        self.import_local_button.pack(side="right")

    def set_gb_description(self, value: str):
        self.gb_description.configure(state="normal")
        self.gb_description.delete("1.0", "end")
        self.gb_description.insert("1.0", value)
        self.gb_description.configure(state="disabled")

    def set_gb_preview_state(self, message: str, *, source: str = "") -> None:
        self._gb_preview_photo = None
        self.gb_preview.configure(image="", text=message)
        self.gb_preview_source.configure(text=source)

    def set_gb_preview_image(
        self,
        image: Image.Image,
        *,
        source: str = "GameBanana preview",
    ) -> None:
        photo = ImageTk.PhotoImage(image)
        self._gb_preview_photo = photo
        self.gb_preview.configure(image=photo, text="")
        self.gb_preview_source.configure(text=source)

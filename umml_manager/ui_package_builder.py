from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .package_builder import PackageDraft, create_package_workspace
from .ui_manifest_editor import launch_manifest_editor
from .ui_windows import present_toplevel


class PackageBuilderDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Create UMML package")
        self.transient(app.root)
        self.resizable(True, True)
        self.minsize(700, 560)
        self.geometry("820x680")

        self.mod_id = tk.StringVar()
        self.title_value = tk.StringVar()
        self.version = tk.StringVar(value="1.0.0")
        self.author = tk.StringVar()
        self.regions = tk.StringVar(value=app.region.get())
        self.characters = tk.StringVar()
        self.dresses = tk.StringVar()
        self.content_types = tk.StringVar(value="model, textures")
        self.tags = tk.StringVar()
        self.dependencies = tk.StringVar()
        self.incompatibilities = tk.StringVar()
        self.load_after = tk.StringVar()
        self.load_before = tk.StringVar()
        self.configurable = tk.BooleanVar(value=False)
        self.character_selector = tk.BooleanVar(value=False)

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text=(
                "Create an editable package workspace. Nothing is imported, enabled, or applied "
                "until you explicitly save it as a package version. Asset preparation is automatic."
            ),
            style="Muted.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        notebook = ttk.Notebook(frame)
        notebook.grid(row=1, column=0, sticky="nsew")
        identity = ttk.Frame(notebook, padding=14)
        targeting = ttk.Frame(notebook, padding=14)
        compatibility = ttk.Frame(notebook, padding=14)
        notebook.add(identity, text="Identity")
        notebook.add(targeting, text="Targets")
        notebook.add(compatibility, text="Compatibility")

        self._build_identity(identity)
        self._build_targeting(targeting)
        self._build_compatibility(compatibility)

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Create and edit",
            style="Accent.TButton",
            command=self._create,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_identity(self, page: ttk.Frame) -> None:
        page.columnconfigure(1, weight=1)
        fields = (
            ("Stable package ID", self.mod_id),
            ("Title", self.title_value),
            ("Version", self.version),
            ("Author", self.author),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(page, text=label).grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(page, textvariable=variable).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(12, 0),
                pady=6,
            )
        ttk.Label(page, text="Description").grid(row=4, column=0, sticky="nw", pady=6)
        self.description = tk.Text(page, height=13, wrap="word")
        self.description.grid(row=4, column=1, sticky="nsew", padx=(12, 0), pady=6)
        page.rowconfigure(4, weight=1)

    def _build_targeting(self, page: ttk.Frame) -> None:
        page.columnconfigure(1, weight=1)
        fields = (
            ("Affected characters", self.characters),
            ("Affected dresses/costumes", self.dresses),
            ("Content types", self.content_types),
            ("Tags", self.tags),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(page, text=label).grid(row=row, column=0, sticky="w", pady=7)
            ttk.Entry(page, textvariable=variable).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(12, 0),
                pady=7,
            )
        ttk.Checkbutton(
            page,
            text="Create a generic two-choice variant template",
            variable=self.configurable,
        ).grid(row=4, column=1, sticky="w", padx=(12, 0), pady=(12, 4))
        ttk.Checkbutton(
            page,
            text="Create a profile-selectable character variant template",
            variable=self.character_selector,
        ).grid(row=5, column=1, sticky="w", padx=(12, 0), pady=4)
        ttk.Label(
            page,
            text=(
                "Character selection controls authored folders such as assets/characters/special-week. "
                "It does not rewrite an arbitrary bundle from one character ID to another."
            ),
            style="Muted.TLabel",
            wraplength=660,
            justify="left",
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def _build_compatibility(self, page: ttk.Frame) -> None:
        page.columnconfigure(1, weight=1)
        fields = (
            ("Regions", self.regions),
            ("Required mods", self.dependencies),
            ("Incompatible mods", self.incompatibilities),
            ("Load after", self.load_after),
            ("Load before", self.load_before),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(page, text=label).grid(row=row, column=0, sticky="w", pady=6)
            ttk.Entry(page, textvariable=variable).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(12, 0),
                pady=6,
            )
        ttk.Label(page, text="Compatibility notes").grid(
            row=5,
            column=0,
            sticky="nw",
            pady=6,
        )
        self.compatibility_notes = tk.Text(page, height=10, wrap="word")
        self.compatibility_notes.grid(
            row=5,
            column=1,
            sticky="nsew",
            padx=(12, 0),
            pady=6,
        )
        page.rowconfigure(5, weight=1)

    def _create(self) -> None:
        draft = PackageDraft(
            mod_id=self.mod_id.get().strip(),
            title=self.title_value.get().strip(),
            version=self.version.get().strip(),
            author=self.author.get().strip(),
            description=self.description.get("1.0", "end").strip(),
            regions=tuple(_split(self.regions.get())),
            target_characters=tuple(_split(self.characters.get())),
            target_dresses=tuple(_split(self.dresses.get())),
            content_types=tuple(_split(self.content_types.get())),
            tags=tuple(_split(self.tags.get())),
            dependencies=tuple(_split(self.dependencies.get())),
            incompatibilities=tuple(_split(self.incompatibilities.get())),
            load_after=tuple(_split(self.load_after.get())),
            load_before=tuple(_split(self.load_before.get())),
            compatibility_notes=self.compatibility_notes.get("1.0", "end").strip(),
            configurable_template=self.configurable.get(),
            character_template=self.character_selector.get(),
        )
        try:
            path = create_package_workspace(self.app.store, draft)
        except Exception as exc:
            messagebox.showerror("Package workspace failed", str(exc), parent=self)
            return
        self.app.status.set(f"Created package workspace at {path}")
        self.destroy()
        self.app.root.after(0, lambda: launch_manifest_editor(self.app, path))


def launch_package_builder(app) -> None:
    if getattr(app, "_busy", False):
        app.status.set("Wait for the current Manager task to finish")
        return
    dialog = PackageBuilderDialog(app)
    present_toplevel(dialog, app.root)


def _split(value: str) -> list[str]:
    normalized = value.replace("\r", "\n").replace(",", "\n").replace(";", "\n")
    return list(dict.fromkeys(item.strip() for item in normalized.split("\n") if item.strip()))

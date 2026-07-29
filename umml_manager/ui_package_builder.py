from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .package_builder import PackageDraft, create_package_workspace
from .studio import open_path


class PackageBuilderDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Create UMML package")
        self.transient(app.root)
        self.resizable(True, False)
        self.minsize(620, 420)

        self.mod_id = tk.StringVar()
        self.title_value = tk.StringVar()
        self.version = tk.StringVar(value="1.0.0")
        self.author = tk.StringVar()
        self.regions = tk.StringVar(value=app.region.get())
        self.configurable = tk.BooleanVar(value=False)

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        fields = (
            ("Stable package ID", self.mod_id),
            ("Title", self.title_value),
            ("Version", self.version),
            ("Author", self.author),
            ("Regions", self.regions),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(frame, textvariable=variable).grid(
                row=row, column=1, sticky="ew", padx=(12, 0), pady=5
            )

        ttk.Label(frame, text="Description").grid(row=5, column=0, sticky="nw", pady=5)
        self.description = tk.Text(frame, height=6, wrap="word")
        self.description.grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=5)

        ttk.Checkbutton(
            frame,
            text="Create a two-choice configurable variant template",
            variable=self.configurable,
        ).grid(row=6, column=1, sticky="w", padx=(12, 0), pady=(8, 4))
        ttk.Label(
            frame,
            text=(
                "This creates an editable workspace only. It is not imported, prepared, "
                "enabled, or applied until you deliberately import it from Library."
            ),
            style="Muted.TLabel",
            wraplength=500,
            justify="left",
        ).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 14))

        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Create workspace",
            style="Accent.TButton",
            command=self._create,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.grab_set()

    def _create(self) -> None:
        regions = tuple(
            value.strip().casefold()
            for value in self.regions.get().split(",")
            if value.strip()
        )
        draft = PackageDraft(
            mod_id=self.mod_id.get().strip(),
            title=self.title_value.get().strip(),
            version=self.version.get().strip(),
            author=self.author.get().strip(),
            description=self.description.get("1.0", "end").strip(),
            regions=regions,
            configurable_template=self.configurable.get(),
        )
        try:
            path = create_package_workspace(self.app.store, draft)
            open_path(path)
        except Exception as exc:
            messagebox.showerror("Package workspace failed", str(exc), parent=self)
            return
        self.app.status.set(f"Created package workspace at {path}")
        self.destroy()


def launch_package_builder(app) -> None:
    if getattr(app, "_busy", False):
        app.status.set("Wait for the current Manager task to finish")
        return
    PackageBuilderDialog(app)

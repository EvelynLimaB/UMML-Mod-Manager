from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from .manifest import normalize_manifest_policy
from .package_builder import build_character_option_group
from .safety import atomic_write_json
from .store import StoreError, sanitize_id
from .studio import open_path


class ManifestEditorDialog(tk.Toplevel):
    """Edit a workspace manifest while leaving imported source versions immutable."""

    def __init__(self, app, workspace: str | Path):
        super().__init__(app.root)
        self.app = app
        self.workspace = Path(workspace).expanduser().resolve()
        self.manifest_path = self.workspace / "umml-mod.json"
        self.original = self._load_manifest()
        self.saved = False
        self.import_requested = False

        self.title("Edit UMML package")
        self.transient(app.root)
        self.resizable(True, True)
        self.minsize(760, 620)
        self.geometry("860x700")

        self.mod_id = tk.StringVar(value=str(self.original.get("id") or ""))
        self.title_value = tk.StringVar(value=str(self.original.get("title") or ""))
        self.version = tk.StringVar(
            value=str(self.original.get("mod_version") or self.original.get("version") or "1.0.0")
        )
        self.author = tk.StringVar(value=str(self.original.get("author") or ""))
        self.regions = tk.StringVar(value=_join(self.original.get("regions", [])))
        targets = self.original.get("targets", {})
        targets = targets if isinstance(targets, dict) else {}
        self.characters = tk.StringVar(value=_join(targets.get("characters", [])))
        self.dresses = tk.StringVar(value=_join(targets.get("dresses", [])))
        self.content_types = tk.StringVar(value=_join(targets.get("content", [])))
        self.tags = tk.StringVar(value=_join(self.original.get("tags", [])))
        self.dependencies = tk.StringVar(value=_join(self.original.get("dependencies", [])))
        self.incompatibilities = tk.StringVar(
            value=_join(self.original.get("incompatibilities", []))
        )
        self.load_after = tk.StringVar(value=_join(self.original.get("load_after", [])))
        self.load_before = tk.StringVar(value=_join(self.original.get("load_before", [])))

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(
            outer,
            text=(
                f"Workspace: {self.workspace}\n"
                "Saving changes only edits this workspace. Import creates a new immutable version; "
                "it never mutates the already imported source."
            ),
            style="Muted.TLabel",
            justify="left",
            wraplength=800,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        notebook = ttk.Notebook(outer)
        notebook.grid(row=1, column=0, sticky="nsew")
        identity = ttk.Frame(notebook, padding=14)
        targeting = ttk.Frame(notebook, padding=14)
        compatibility = ttk.Frame(notebook, padding=14)
        options = ttk.Frame(notebook, padding=14)
        notebook.add(identity, text="Identity")
        notebook.add(targeting, text="Targets")
        notebook.add(compatibility, text="Compatibility")
        notebook.add(options, text="Options")

        self._build_identity(identity)
        self._build_targeting(targeting)
        self._build_compatibility(compatibility)
        self._build_options(options)

        buttons = ttk.Frame(outer)
        buttons.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Open folder", command=self._open_folder).pack(side="left")
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Save and import",
            style="Accent.TButton",
            command=self._save_and_import,
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            buttons,
            text="Save manifest",
            command=self._save,
        ).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()

    def _build_identity(self, page: ttk.Frame) -> None:
        page.columnconfigure(1, weight=1)
        fields = (
            ("Stable package ID", self.mod_id),
            ("Title", self.title_value),
            ("Version", self.version),
            ("Author", self.author),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(page, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(page, textvariable=variable).grid(
                row=row,
                column=1,
                sticky="ew",
                padx=(12, 0),
                pady=5,
            )
        ttk.Label(page, text="Description").grid(row=4, column=0, sticky="nw", pady=5)
        self.description = tk.Text(page, height=14, wrap="word")
        self.description.grid(row=4, column=1, sticky="nsew", padx=(12, 0), pady=5)
        self.description.insert("1.0", str(self.original.get("description") or ""))
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
        ttk.Label(
            page,
            text=(
                "Use comma or new-line separated IDs/names. These fields describe authored targets "
                "for search and compatibility. They do not magically retarget arbitrary Unity bundles. "
                "For selectable character variants, generate a character option group below."
            ),
            style="Muted.TLabel",
            wraplength=680,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 8))
        ttk.Button(
            page,
            text="Generate character selector",
            command=self._generate_character_selector,
        ).grid(row=5, column=1, sticky="w", padx=(12, 0), pady=6)

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
        self.compatibility_notes.insert(
            "1.0",
            str(self.original.get("compatibility_notes") or ""),
        )
        page.rowconfigure(5, weight=1)
        ttk.Label(
            page,
            text=(
                "Dependencies and incompatibilities are hard blockers. Load-before/after constraints "
                "become blockers only when both referenced mods are enabled in the wrong order."
            ),
            style="Muted.TLabel",
            wraplength=680,
            justify="left",
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def _build_options(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        ttk.Label(
            page,
            text=(
                "Advanced profile-scoped option groups. Each choice includes creator-facing assets/ "
                "patterns. Preparation maps those sources to final game hashes; profile changes only "
                "filter the resolved claims."
            ),
            style="Muted.TLabel",
            wraplength=720,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.options_json = tk.Text(page, wrap="none", font=("TkFixedFont", 10))
        self.options_json.grid(row=1, column=0, sticky="nsew")
        self.options_json.insert(
            "1.0",
            json.dumps(self.original.get("option_groups", {}), indent=2, ensure_ascii=False),
        )
        scroll = ttk.Scrollbar(page, orient="vertical", command=self.options_json.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.options_json.configure(yscrollcommand=scroll.set)

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            raise StoreError(f"Workspace manifest not found: {self.manifest_path}")
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"Could not read workspace manifest: {exc}") from exc
        if not isinstance(value, dict):
            raise StoreError("Workspace manifest must contain a JSON object")
        return dict(value)

    def _manifest_value(self) -> dict[str, Any]:
        mod_id = self.mod_id.get().strip().casefold()
        if not mod_id or sanitize_id(mod_id) != mod_id:
            raise StoreError(
                "Package ID must be lowercase and use letters, digits, dots, underscores, or hyphens."
            )
        title = self.title_value.get().strip()
        version = self.version.get().strip()
        if not title:
            raise StoreError("Package title cannot be empty")
        if not version:
            raise StoreError("Package version cannot be empty")
        try:
            option_groups = json.loads(self.options_json.get("1.0", "end").strip() or "{}")
        except json.JSONDecodeError as exc:
            raise StoreError(f"Option-group JSON is invalid: {exc}") from exc
        if not isinstance(option_groups, dict):
            raise StoreError("option_groups must be a JSON object")

        manifest = dict(self.original)
        manifest.update(
            {
                "id": mod_id,
                "title": title,
                "mod_version": version,
                "author": self.author.get().strip(),
                "description": self.description.get("1.0", "end").strip(),
                "regions": _split(self.regions.get()),
                "targets": {
                    "characters": _split(self.characters.get()),
                    "dresses": _split(self.dresses.get()),
                    "content": _split(self.content_types.get()),
                },
                "tags": _split(self.tags.get()),
                "dependencies": _split(self.dependencies.get()),
                "incompatibilities": _split(self.incompatibilities.get()),
                "load_after": _split(self.load_after.get()),
                "load_before": _split(self.load_before.get()),
                "compatibility_notes": self.compatibility_notes.get("1.0", "end").strip(),
                "option_groups": option_groups,
            }
        )
        policy = normalize_manifest_policy(manifest, mod_id=mod_id)
        manifest.update(
            {
                "regions": policy.regions,
                "targets": policy.targets,
                "tags": policy.tags,
                "dependencies": policy.dependencies,
                "incompatibilities": policy.incompatibilities,
                "load_after": policy.load_after,
                "load_before": policy.load_before,
                "compatibility_notes": policy.compatibility_notes,
                "option_groups": policy.option_groups,
            }
        )
        return manifest

    def _save(self) -> bool:
        try:
            manifest = self._manifest_value()
            atomic_write_json(self.manifest_path, manifest)
        except Exception as exc:
            messagebox.showerror("Manifest validation failed", str(exc), parent=self)
            return False
        self.original = manifest
        self.saved = True
        self.app.status.set(f"Saved package manifest at {self.manifest_path}")
        messagebox.showinfo(
            "Manifest saved",
            "The editable workspace was updated. Imported source versions were not changed.",
            parent=self,
        )
        return True

    def _save_and_import(self) -> None:
        if not self._save():
            return
        self.import_requested = True
        self.destroy()

    def _generate_character_selector(self) -> None:
        characters = _split(self.characters.get())
        if not characters:
            messagebox.showwarning(
                "Characters required",
                "Enter one or more affected characters before generating the selector.",
                parent=self,
            )
            return
        try:
            groups = json.loads(self.options_json.get("1.0", "end").strip() or "{}")
            if not isinstance(groups, dict):
                raise ValueError("option_groups must be an object")
        except (json.JSONDecodeError, ValueError) as exc:
            messagebox.showerror("Invalid option JSON", str(exc), parent=self)
            return
        if "character" in groups and not messagebox.askyesno(
            "Replace character selector?",
            "The manifest already has a character option group. Replace it?",
            parent=self,
        ):
            return
        group, directory_ids = build_character_option_group(characters)
        groups["character"] = group
        assets = self.workspace / "assets"
        for choice_id in directory_ids:
            (assets / "characters" / choice_id).mkdir(parents=True, exist_ok=True)
        (assets / "common").mkdir(parents=True, exist_ok=True)
        self.options_json.delete("1.0", "end")
        self.options_json.insert("1.0", json.dumps(groups, indent=2, ensure_ascii=False))
        self.app.status.set(
            "Generated a profile character selector and matching workspace directories"
        )

    def _open_folder(self) -> None:
        try:
            open_path(self.workspace)
        except Exception as exc:
            messagebox.showerror("Could not open workspace", str(exc), parent=self)


def launch_manifest_editor(app, workspace: str | Path) -> ManifestEditorDialog | None:
    try:
        dialog = ManifestEditorDialog(app, workspace)
    except Exception as exc:
        messagebox.showerror("Could not open package editor", str(exc), parent=app.root)
        return None
    app.root.wait_window(dialog)
    if dialog.import_requested:
        app._import(lambda: app.store.import_folder(dialog.workspace))
    return dialog


def edit_selected_package(app, page) -> None:
    if getattr(app, "_busy", False):
        app.status.set("Wait for the current Manager task to finish")
        return
    mod_id = page.selected_id()
    if not mod_id:
        app.status.set("Select a mod before creating an editable package copy")
        return
    try:
        workspace = app.store.create_workspace(mod_id)
    except Exception as exc:
        messagebox.showerror("Workspace failed", str(exc), parent=app.root)
        return
    app.status.set(f"Created editable package copy at {workspace}")
    launch_manifest_editor(app, workspace)


def _split(value: str) -> list[str]:
    normalized = value.replace("\r", "\n").replace(",", "\n").replace(";", "\n")
    return list(dict.fromkeys(item.strip() for item in normalized.split("\n") if item.strip()))


def _join(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if str(item).strip())
    return ""

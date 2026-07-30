from __future__ import annotations

import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from .manifest import normalize_manifest_policy
from .mod_inspection import ModInspection, build_component_option_groups, inspect_mod
from .safety import atomic_write_json
from .studio import open_path
from .store import StoreError
from .ui_manifest_editor import ManifestEditorDialog, _ensure_workspace_manifest


_GENERATED_GROUPS = re.compile(r"^(?:components|detected-variant-\d+)$")


class ModInspectorDialog(tk.Toplevel):
    """Inspect mapped assets and edit common package metadata without touching JSON."""

    def __init__(self, app, record, workspace: str | Path):
        super().__init__(app.root)
        self.app = app
        self.record = record
        self.workspace = Path(workspace).expanduser().resolve()
        self.manifest_path = self.workspace / "umml-mod.json"
        self.manifest = self._load_manifest()
        self.inspection = inspect_mod(record)
        self.import_requested = False

        self.title(f"Inspect and edit · {record.name}")
        self.transient(app.root)
        self.resizable(True, True)
        self.minsize(920, 640)
        self.geometry("1040x760")

        targets = self.manifest.get("targets", {})
        targets = targets if isinstance(targets, dict) else {}
        self.mod_id = tk.StringVar(value=str(self.manifest.get("id") or record.id))
        self.version = tk.StringVar(
            value=_next_local_version(
                str(
                    self.manifest.get("mod_version")
                    or self.manifest.get("version")
                    or record.version
                )
            )
        )
        self.title_value = tk.StringVar(
            value=str(self.manifest.get("title") or record.name)
        )
        self.author = tk.StringVar(
            value=str(self.manifest.get("author") or record.author)
        )
        self.characters = tk.StringVar(value=_join(targets.get("characters", [])))
        self.dresses = tk.StringVar(value=_join(targets.get("dresses", [])))
        self.content_types = tk.StringVar(value=_join(targets.get("content", [])))
        self.tags = tk.StringVar(value=_join(self.manifest.get("tags", [])))
        self.regions = tk.StringVar(value=_join(self.manifest.get("regions", [])))
        self.dependencies = tk.StringVar(
            value=_join(self.manifest.get("dependencies", []))
        )
        self.incompatibilities = tk.StringVar(
            value=_join(self.manifest.get("incompatibilities", []))
        )
        self.load_after = tk.StringVar(value=_join(self.manifest.get("load_after", [])))
        self.load_before = tk.StringVar(
            value=_join(self.manifest.get("load_before", []))
        )
        self.component_controls = tk.BooleanVar(value=False)

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        ttk.Label(
            outer,
            text=record.name,
            style="PageTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            outer,
            text=(
                self.inspection.summary()
                + "\nThe Manager uses prepared source-to-target mappings. Detected IDs and parts are "
                "suggestions; saving creates a new immutable package version."
            ),
            style="Muted.TLabel",
            justify="left",
            wraplength=940,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 12))

        notebook = ttk.Notebook(outer)
        notebook.grid(row=2, column=0, sticky="nsew")
        detected = ttk.Frame(notebook, padding=14)
        package = ttk.Frame(notebook, padding=14)
        compatibility = ttk.Frame(notebook, padding=14)
        components = ttk.Frame(notebook, padding=14)
        notebook.add(detected, text="Detected changes")
        notebook.add(package, text="Package details")
        notebook.add(compatibility, text="Compatibility")
        notebook.add(components, text="Components")

        self._build_detected(detected)
        self._build_package(package)
        self._build_compatibility(compatibility)
        self._build_components(components)

        actions = ttk.Frame(outer)
        actions.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        ttk.Button(
            actions,
            text="Open files externally",
            command=self._open_folder,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Advanced editor",
            command=self._advanced_editor,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            actions,
            text="Save as new version",
            style="Accent.TButton",
            command=self._save_and_import,
        ).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())

    def _build_detected(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        summary = []
        if self.inspection.character_ids:
            summary.append("Character IDs: " + ", ".join(self.inspection.character_ids))
        if self.inspection.dress_ids:
            summary.append("Dress IDs: " + ", ".join(self.inspection.dress_ids))
        if self.inspection.content_types:
            summary.append("Content: " + ", ".join(self.inspection.content_types))
        if self.inspection.parts:
            summary.append("Parts: " + ", ".join(self.inspection.parts))
        if self.inspection.warnings:
            summary.extend(self.inspection.warnings)
        ttk.Label(
            page,
            text="\n".join(summary) or "No reliable asset metadata was detected yet.",
            style="Muted.TLabel",
            justify="left",
            wraplength=900,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 10))

        table_frame = ttk.Frame(page)
        table_frame.grid(row=1, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(
            table_frame,
            columns=("type", "part", "target"),
            show="tree headings",
            selectmode="browse",
        )
        tree.heading("#0", text="Source asset")
        tree.heading("type", text="Type")
        tree.heading("part", text="Part")
        tree.heading("target", text="Game target")
        tree.column("#0", width=390, anchor="w")
        tree.column("type", width=100, anchor="center")
        tree.column("part", width=140, anchor="w")
        tree.column("target", width=210, anchor="w")
        for index, finding in enumerate(self.inspection.findings):
            tree.insert(
                "",
                "end",
                iid=f"asset-{index}",
                text=finding.source,
                values=(
                    finding.content_type,
                    finding.part,
                    finding.target or "not mapped",
                ),
            )
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        ttk.Button(
            page,
            text="Use detected IDs and content",
            command=self._use_detected_metadata,
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

    def _build_package(self, page: ttk.Frame) -> None:
        page.columnconfigure(1, weight=1)
        fields = (
            ("Package ID", self.mod_id),
            ("New version", self.version),
            ("Title", self.title_value),
            ("Author", self.author),
            ("Affected characters / IDs", self.characters),
            ("Affected dresses / IDs", self.dresses),
            ("Content types", self.content_types),
            ("Tags", self.tags),
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
        ttk.Label(page, text="Description").grid(row=8, column=0, sticky="nw", pady=5)
        self.description = tk.Text(page, height=10, wrap="word")
        self.description.grid(
            row=8,
            column=1,
            sticky="nsew",
            padx=(12, 0),
            pady=5,
        )
        self.description.insert(
            "1.0",
            str(self.manifest.get("description") or self.record.description or ""),
        )
        page.rowconfigure(8, weight=1)

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
        self.compatibility_notes = tk.Text(page, height=12, wrap="word")
        self.compatibility_notes.grid(
            row=5,
            column=1,
            sticky="nsew",
            padx=(12, 0),
            pady=6,
        )
        self.compatibility_notes.insert(
            "1.0",
            str(self.manifest.get("compatibility_notes") or ""),
        )
        page.rowconfigure(5, weight=1)

    def _build_components(self, page: ttk.Frame) -> None:
        page.columnconfigure(0, weight=1)
        ttk.Label(
            page,
            text=(
                "The Manager can turn detected source files into profile controls. Files with unique "
                "targets become checkboxes. Files that replace the same target become a single-choice "
                "variant selector. This does not rewrite bundles or invent character conversions."
            ),
            style="Muted.TLabel",
            justify="left",
            wraplength=850,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Checkbutton(
            page,
            text="Create simple profile controls for detected components",
            variable=self.component_controls,
            command=self._refresh_component_preview,
        ).grid(row=1, column=0, sticky="w")
        self.component_preview = tk.Text(page, height=20, wrap="word")
        self.component_preview.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.component_preview.configure(state="disabled")
        page.rowconfigure(2, weight=1)
        self._refresh_component_preview()

    def _refresh_component_preview(self) -> None:
        lines: list[str] = []
        if not self.inspection.findings:
            lines.append("No mapped source files are available. Prepare the mod first.")
        else:
            by_target: dict[str, list[str]] = {}
            for finding in self.inspection.findings:
                by_target.setdefault(finding.target, []).append(finding.label)
            optional = [labels[0] for labels in by_target.values() if len(labels) == 1]
            variants = [labels for labels in by_target.values() if len(labels) > 1]
            lines.append(f"Optional component checkboxes: {len(optional)}")
            lines.extend(f"  • {label}" for label in optional[:20])
            if len(optional) > 20:
                lines.append(f"  • … and {len(optional) - 20} more")
            lines.append("")
            lines.append(f"Mutually exclusive variant groups: {len(variants)}")
            for labels in variants[:10]:
                lines.append("  • " + " / ".join(labels))
        if not self.component_controls.get():
            lines.insert(0, "Component controls are currently disabled.\n")
        self.component_preview.configure(state="normal")
        self.component_preview.delete("1.0", "end")
        self.component_preview.insert("1.0", "\n".join(lines))
        self.component_preview.configure(state="disabled")

    def _use_detected_metadata(self) -> None:
        if self.inspection.character_ids:
            self.characters.set(_merge_text(self.characters.get(), self.inspection.character_ids))
        if self.inspection.dress_ids:
            self.dresses.set(_merge_text(self.dresses.get(), self.inspection.dress_ids))
        if self.inspection.content_types:
            self.content_types.set(
                _merge_text(self.content_types.get(), self.inspection.content_types)
            )
        inferred_tags = tuple(
            dict.fromkeys((*self.inspection.parts, *self.inspection.content_types))
        )
        if inferred_tags:
            self.tags.set(_merge_text(self.tags.get(), inferred_tags))
        self.app.status.set(f"Applied detected metadata suggestions for {self.record.name}")

    def _manifest_value(self) -> dict[str, Any]:
        mod_id = self.mod_id.get().strip().casefold()
        version = self.version.get().strip()
        title = self.title_value.get().strip()
        if not mod_id:
            raise StoreError("Package ID cannot be empty")
        if not version:
            raise StoreError("Version cannot be empty")
        if not title:
            raise StoreError("Title cannot be empty")
        if (mod_id, version) == (self.record.id, self.record.version):
            raise StoreError(
                "Edited metadata must be imported as a new immutable version or package ID."
            )

        manifest = dict(self.manifest)
        raw_groups = manifest.get("option_groups", {})
        groups = dict(raw_groups) if isinstance(raw_groups, dict) else {}
        if self.component_controls.get():
            preserved = {
                key: value
                for key, value in groups.items()
                if not _GENERATED_GROUPS.fullmatch(str(key))
            }
            groups = build_component_option_groups(
                self.inspection,
                preserve=preserved,
            )
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
                "compatibility_notes": self.compatibility_notes.get(
                    "1.0", "end"
                ).strip(),
                "option_groups": groups,
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

    def _save_workspace(self) -> bool:
        try:
            manifest = self._manifest_value()
            atomic_write_json(self.manifest_path, manifest)
        except Exception as exc:
            messagebox.showerror("Package validation failed", str(exc), parent=self)
            return False
        self.manifest = manifest
        return True

    def _save_and_import(self) -> None:
        if self.component_controls.get() and not self.inspection.findings:
            messagebox.showwarning(
                "Prepare the mod first",
                "Component controls need a real source-to-target mapping. Re-prepare the mod, then inspect it again.",
                parent=self,
            )
            return
        if not self._save_workspace():
            return
        self.import_requested = True
        self.destroy()

    def _advanced_editor(self) -> None:
        if not self._save_workspace():
            return
        self.withdraw()
        dialog = ManifestEditorDialog(self.app, self.workspace)
        present_toplevel(dialog, self.app.root)
        self.app.root.wait_window(dialog)
        if dialog.import_requested:
            self.import_requested = True
            self.destroy()
            return
        try:
            self.manifest = self._load_manifest()
        except Exception as exc:
            messagebox.showerror("Could not reload manifest", str(exc), parent=self)
        self.deiconify()
        present_toplevel(self, self.app.root)

    def _open_folder(self) -> None:
        try:
            open_path(self.workspace)
        except Exception as exc:
            messagebox.showerror("Could not open workspace", str(exc), parent=self)

    def _load_manifest(self) -> dict[str, Any]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"Could not read workspace manifest: {exc}") from exc
        if not isinstance(value, dict):
            raise StoreError("Workspace manifest must contain a JSON object")
        return dict(value)


def inspect_selected_mod(app, page) -> None:
    if getattr(app, "_busy", False):
        app.status.set("Wait for the current Manager task to finish")
        return
    mod_id = page.selected_id()
    if not mod_id:
        app.status.set("Select a mod to inspect and edit")
        return
    try:
        record = app.store.get_mod(mod_id)
        workspace = app.store.create_workspace(mod_id)
        _ensure_workspace_manifest(workspace, record)
        dialog = ModInspectorDialog(app, record, workspace)
    except Exception as exc:
        messagebox.showerror("Could not inspect mod", str(exc), parent=app.root)
        return

    app.status.set(f"Inspecting {record.name} in editable workspace {workspace}")
    present_toplevel(dialog, app.root)
    app.root.wait_window(dialog)
    if dialog.import_requested:
        app._import(lambda: app.store.import_folder(workspace))


def present_toplevel(dialog: tk.Toplevel, parent: tk.Misc) -> None:
    """Center, raise, and focus a Manager-owned window without leaving it topmost."""

    try:
        dialog.update_idletasks()
        parent_top = parent.winfo_toplevel()
        width = max(dialog.winfo_reqwidth(), dialog.winfo_width())
        height = max(dialog.winfo_reqheight(), dialog.winfo_height())
        x = parent_top.winfo_rootx() + max(24, (parent_top.winfo_width() - width) // 2)
        y = parent_top.winfo_rooty() + max(24, (parent_top.winfo_height() - height) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.deiconify()
        dialog.lift(parent_top)
        try:
            dialog.attributes("-topmost", True)
            dialog.after(180, lambda: _clear_topmost(dialog))
        except tk.TclError:
            pass
        dialog.focus_force()
        dialog.grab_set()
    except tk.TclError:
        return


def _clear_topmost(dialog: tk.Toplevel) -> None:
    try:
        if dialog.winfo_exists():
            dialog.attributes("-topmost", False)
            dialog.lift()
            dialog.focus_force()
    except tk.TclError:
        pass


def _next_local_version(value: str) -> str:
    base = value.strip() or "1.0.0"
    match = re.fullmatch(r"(.+?)\+local(\d+)", base, re.I)
    if match:
        return f"{match.group(1)}+local{int(match.group(2)) + 1}"
    return f"{base}+local1"


def _split(value: str) -> list[str]:
    normalized = value.replace("\r", "\n").replace(",", "\n").replace(";", "\n")
    return list(dict.fromkeys(item.strip() for item in normalized.split("\n") if item.strip()))


def _join(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value if str(item).strip())
    return ""


def _merge_text(current: str, additions: tuple[str, ...]) -> str:
    return ", ".join(dict.fromkeys((*_split(current), *additions)))

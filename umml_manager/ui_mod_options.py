from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from .options import OptionError, normalize_profile_options, option_summary
from .ui_windows import present_toplevel


class ModOptionsDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        mod_name: str,
        groups: dict[str, dict[str, Any]],
        current: dict[str, list[str]],
    ):
        super().__init__(parent)
        self.title(f"Configure {mod_name}")
        self.transient(parent.winfo_toplevel())
        self.resizable(True, True)
        self.minsize(560, 400)
        self.result: dict[str, list[str]] | None = None
        self.groups = groups
        self.single_vars: dict[str, tk.StringVar] = {}
        self.multiple_vars: dict[str, dict[str, tk.BooleanVar]] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=16)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        content = ttk.Frame(canvas)
        content.columnconfigure(0, weight=1)
        window = canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        def resized(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window, width=canvas.winfo_width())

        content.bind("<Configure>", resized)
        canvas.bind("<Configure>", resized)

        row = 0
        ttk.Label(
            content,
            text=(
                "Selections are stored only in this profile. Changing them does not modify the "
                "imported package. The Manager resolves and applies the selected source bundles automatically."
            ),
            style="Muted.TLabel",
            wraplength=700,
            justify="left",
        ).grid(row=row, column=0, sticky="ew", pady=(0, 12))
        row += 1

        for group_id, group in groups.items():
            kind = str(group.get("kind") or "generic")
            kind_label = _kind_label(kind)
            title = str(group.get("name") or group_id)
            if kind_label and kind != "generic":
                title += f" • {kind_label}"
            frame = ttk.LabelFrame(content, text=title, padding=12)
            frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            frame.columnconfigure(0, weight=1)
            description = str(group.get("description") or "").strip()
            item_row = 0
            if description:
                ttk.Label(
                    frame,
                    text=description,
                    style="SurfaceMuted.TLabel",
                    wraplength=660,
                    justify="left",
                ).grid(row=item_row, column=0, sticky="w", pady=(0, 8))
                item_row += 1

            selected = set(current.get(group_id, []))
            choices = dict(group.get("choices", {}))
            if group.get("type") == "single":
                default = list(group.get("default", [""]))
                variable = tk.StringVar(
                    value=next(iter(selected), str(default[0] if default else ""))
                )
                self.single_vars[group_id] = variable
                for choice_id, choice in choices.items():
                    ttk.Radiobutton(
                        frame,
                        text=_choice_label(choice_id, choice),
                        variable=variable,
                        value=choice_id,
                    ).grid(row=item_row, column=0, sticky="w", pady=3)
                    item_row += 1
            else:
                variables: dict[str, tk.BooleanVar] = {}
                self.multiple_vars[group_id] = variables
                for choice_id, choice in choices.items():
                    variable = tk.BooleanVar(value=choice_id in selected)
                    variables[choice_id] = variable
                    ttk.Checkbutton(
                        frame,
                        text=_choice_label(choice_id, choice),
                        variable=variable,
                    ).grid(row=item_row, column=0, sticky="w", pady=3)
                    item_row += 1
            row += 1

        buttons = ttk.Frame(outer)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons,
            text="Save profile options",
            style="Accent.TButton",
            command=self._save,
        ).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._save())
        present_toplevel(self, parent)

    def _save(self) -> None:
        raw: dict[str, Any] = {}
        for group_id, variable in self.single_vars.items():
            raw[group_id] = variable.get()
        for group_id, variables in self.multiple_vars.items():
            raw[group_id] = [
                choice_id
                for choice_id, variable in variables.items()
                if variable.get()
            ]
        try:
            self.result = normalize_profile_options(self.groups, raw)
        except OptionError as exc:
            messagebox.showerror("Invalid mod options", str(exc), parent=self)
            return
        self.destroy()


def configure_mod_options(app, page) -> None:
    if getattr(app, "_busy", False):
        app.status.set("Wait for the current Manager task to finish")
        return
    mod_id = page.selected_id()
    if not mod_id:
        app.status.set("Select a configurable mod first")
        return
    try:
        record = app.store.get_mod(mod_id)
        if not record.option_groups:
            app.status.set(f"{record.name} does not declare configurable options")
            return
        profile = app.profile()
        current = normalize_profile_options(
            record.option_groups,
            profile.options.get(mod_id, {}),
        )
    except Exception as exc:
        messagebox.showerror("Could not load mod options", str(exc), parent=app.root)
        return

    dialog = ModOptionsDialog(
        app.root,
        mod_name=record.name,
        groups=record.option_groups,
        current=current,
    )
    app.root.wait_window(dialog)
    if dialog.result is None:
        return

    profile.options[mod_id] = {
        group_id: list(selected)
        for group_id, selected in dialog.result.items()
    }
    app.store.save_profile(profile)
    page.refresh_option_state(record=record, profile=profile)
    app.refresh()
    if page.tree.exists(mod_id):
        page.tree.selection_set(mod_id)
        page.tree.see(mod_id)
        app.show_selected_mod()
        page.refresh_option_state(record=record, profile=profile)
    app.status.set(
        f"Saved options for {record.name}: "
        f"{option_summary(record.option_groups, dialog.result)}"
    )


def _kind_label(value: str) -> str:
    return {
        "character": "Character",
        "dress": "Dress / costume",
        "color": "Colour",
        "audio": "Audio",
        "quality": "Quality",
        "variant": "Variant",
        "feature": "Feature",
        "generic": "",
    }.get(value, value.replace("-", " ").replace("_", " ").title())


def _choice_label(choice_id: str, choice: dict[str, Any]) -> str:
    label = str(choice.get("name") or choice_id)
    target = str(choice.get("target") or "").strip()
    detail = str(choice.get("description") or "").strip()
    if target and target.casefold() != label.casefold():
        label += f" [{target}]"
    if detail:
        label += f" · {detail}"
    return label

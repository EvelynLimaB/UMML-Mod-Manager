from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from .legacy_adapter import LegacyAssetAdapter
from .models import PACKAGE_UMML_ASSETS
from .ui_maintenance_actions import MaintenanceActions


class AutoPrepareActions(MaintenanceActions):
    """Automatically prepare compatible imports while keeping apply explicit."""

    def refresh_action_states(self) -> None:
        super().refresh_action_states()
        if self._closing or not hasattr(self, "library"):
            return
        busy = bool(self._busy)
        self._configure_button(
            self.library.new_package_button,
            enabled=not busy,
        )
        selected = self.library.selected_id()
        self._configure_button(
            self.library.edit_package_button,
            enabled=bool(selected) and not busy,
        )

    def show_selected_mod(self):
        result = super().show_selected_mod()
        mod_id = self.library.selected_id() if hasattr(self, "library") else None
        if not mod_id:
            return result
        try:
            record = self.store.get_mod(mod_id)
            current = self.library.description.get("1.0", "end").strip()
        except Exception:
            return result

        extra: list[str] = []
        if record.targets:
            rendered = []
            for category, values in sorted(record.targets.items()):
                label = category.replace("_", " ").replace("-", " ").title()
                rendered.append(f"{label}: {', '.join(values)}")
            extra.append("Authored targets\n" + "\n".join(rendered))
        if record.tags:
            extra.append("Tags: " + ", ".join(record.tags))
        if record.load_after:
            extra.append("Load after: " + ", ".join(record.load_after))
        if record.load_before:
            extra.append("Load before: " + ", ".join(record.load_before))
        if record.compatibility_notes:
            extra.append("Compatibility notes\n" + record.compatibility_notes)
        if extra:
            self.library.set_description(current + "\n\n" + "\n\n".join(extra))
        return result

    def render_plan(self):
        result = super().render_plan()
        try:
            resolution = self.current_resolution()
            if not resolution.load_order_conflicts:
                return result
            current = self.plan_text.get("1.0", "end").rstrip()
            heading = "Relative load-order constraints"
            addition = "\n\n" + heading + "\n" + "-" * len(heading)
            addition += "\n" + "\n".join(
                f"• {value}" for value in resolution.load_order_conflicts
            )
            self._set_text(self.plan_text, current + addition)
        except Exception:
            return result
        return result

    def _finish_import(self, record):
        super()._finish_import(record)
        if not should_prepare_automatically(record, self.meta_path.get()):
            if record.package_type == PACKAGE_UMML_ASSETS:
                self.status.set(
                    f"Imported {record.name}; preparation is waiting for valid metadata"
                )
            self.refresh_action_states()
            return

        self._run_task(
            f"Imported {record.name}; preparing assets automatically…",
            lambda: LegacyAssetAdapter(
                self.store,
                self.meta_path.get(),
            ).prepare(record),
            self._finish_automatic_preparation,
            failed=lambda exc: self._automatic_preparation_failed(record, exc),
        )

    def _finish_automatic_preparation(self, prepared):
        self.refresh()
        if self.library.tree.exists(prepared.id):
            self.library.tree.selection_set(prepared.id)
            self.library.tree.see(prepared.id)
            self.show_selected_mod()
        self.status.set(
            f"Imported and prepared {prepared.name}: {len(prepared.files)} asset(s)"
        )
        self.show_page("library")
        self.refresh_action_states()

    def _automatic_preparation_failed(self, record, exc: Exception):
        self.refresh()
        if self.library.tree.exists(record.id):
            self.library.tree.selection_set(record.id)
            self.library.tree.see(record.id)
            self.show_selected_mod()
        self.status.set(
            f"Imported {record.name}, but automatic preparation needs attention"
        )
        messagebox.showwarning(
            "Imported, but preparation failed",
            f"{record.name} was preserved safely in Library, but its assets could "
            f"not be prepared automatically. You can retry with Prepare now.\n\n{exc}",
            parent=self.root,
        )
        self.show_page("library")
        self.refresh_action_states()


def should_prepare_automatically(record, meta_path: str) -> bool:
    return bool(
        record.package_type == PACKAGE_UMML_ASSETS
        and not record.files
        and Path(meta_path).expanduser().is_file()
    )

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from .legacy_adapter import LegacyAssetAdapter
from .models import PACKAGE_UMML_ASSETS
from .ui_maintenance_actions import MaintenanceActions


class AutoPrepareActions(MaintenanceActions):
    """Automatically prepare compatible imports while keeping apply explicit."""

    def refresh(self):
        """Extend Library search without duplicating its ordering and UI logic."""

        if not hasattr(self, "search_library") or not hasattr(self, "library"):
            return super().refresh()
        query = self.search_library.get()
        needle = query.casefold().strip()
        if not needle:
            return super().refresh()

        # The historical Library refresh filters only common metadata. Populate
        # its normal ordered rows with an empty query, then apply the richer
        # package-policy corpus. This keeps one source of truth for ordering,
        # status, selection, and profile counts while making targets and choices
        # genuinely searchable rather than merely documented as such.
        self.search_library.set("")
        try:
            result = super().refresh()
        finally:
            self.search_library.set(query)

        tree = self.library.tree
        for mod_id in tuple(tree.get_children()):
            try:
                record = self.store.get_mod(mod_id)
                matches = needle in self._package_search_text(record)
            except Exception:
                matches = False
            if not matches:
                tree.delete(mod_id)
        visible = len(tree.get_children())
        profile = self.profile()
        self.status.set(
            f"{visible} matching mod(s); {len(profile.enabled)} enabled in "
            f"{profile.name}"
        )
        if not tree.selection():
            self.library.clear_details()
        self.refresh_action_states()
        return result

    @staticmethod
    def _package_search_text(record) -> str:
        target_terms = [*record.targets.keys()]
        target_terms.extend(
            value
            for values in record.targets.values()
            for value in values
        )
        option_terms: list[str] = []
        for group_id, group in record.option_groups.items():
            option_terms.extend(
                [
                    group_id,
                    str(group.get("name") or ""),
                    str(group.get("kind") or ""),
                ]
            )
            for choice_id, choice in dict(group.get("choices", {})).items():
                option_terms.extend(
                    [
                        choice_id,
                        str(choice.get("name") or ""),
                        str(choice.get("target") or ""),
                        str(choice.get("description") or ""),
                    ]
                )
        return " ".join(
            [
                record.name,
                record.author,
                record.id,
                record.description,
                record.package_type,
                *record.regions,
                *record.tags,
                *target_terms,
                *record.dependencies,
                *record.incompatibilities,
                *record.load_after,
                *record.load_before,
                record.compatibility_notes,
                *option_terms,
            ]
        ).casefold()

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

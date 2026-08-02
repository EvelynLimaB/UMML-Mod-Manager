from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .legacy_adapter import LegacyAssetAdapter
from .models import PACKAGE_UMML_ASSETS
from .ui_maintenance_actions import MaintenanceActions


class AutoPrepareActions(MaintenanceActions):
    """Prepare, refresh, and index compatible mods without user maintenance buttons."""

    def refresh(self):
        if not hasattr(self, "search_library") or not hasattr(self, "library"):
            result = super().refresh()
            self._schedule_auto_prepare_scan()
            return result

        query = self.search_library.get()
        needle = query.casefold().strip()
        if not needle:
            result = super().refresh()
            self._schedule_auto_prepare_scan()
            return result

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
            f"{visible} matching mod(s); {len(profile.enabled)} enabled in {profile.name}"
        )
        if not tree.selection():
            self.library.clear_details()
        self.refresh_action_states()
        self._schedule_auto_prepare_scan()
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

    def _mod_status(self, mod) -> str:
        """Replace maintenance jargon with the actual automatic queue state."""

        if mod.package_type != PACKAGE_UMML_ASSETS:
            return f"{mod.package_type}; backend needed"
        if not self._record_needs_auto_prepare(mod):
            # A direct Inspect & edit retry can complete outside the background
            # callback. Do not let an old in-memory error outlive the repaired
            # record and keep the UI permanently labelled as broken.
            self._clear_auto_prepare_error(mod.id)
            return "ready"
        if self._auto_prepare_errors().get(mod.id):
            return "automatic preparation issue"
        return "preparing automatically"

    def refresh_action_states(self) -> None:
        super().refresh_action_states()
        if self._closing or not hasattr(self, "library"):
            return
        busy = bool(self._busy)
        self._configure_button(self.library.new_package_button, enabled=not busy)
        selected = self.library.selected_id()
        self._configure_button(
            self.library.edit_package_button,
            enabled=bool(selected) and not busy,
        )

    def show_selected_mod(self):
        mod_id = self.library.selected_id() if hasattr(self, "library") else None
        if mod_id:
            try:
                selected = self.store.get_mod(mod_id)
                if not self._record_needs_auto_prepare(selected):
                    self._clear_auto_prepare_error(selected.id)
            except Exception:
                pass

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

        needs_prepare = self._record_needs_auto_prepare(record)
        error = self._auto_prepare_errors().get(record.id) if needs_prepare else None
        if error:
            extra.append(
                "Automatic preparation issue\n"
                + error
                + "\nThe imported source is unchanged. The Manager will retry after a restart or update, "
                "after metadata or package changes, or when Inspect & edit is opened again."
            )
        elif needs_prepare:
            extra.append(
                "Automatic preparation\nQueued. No manual Prepare or Re-prepare action is required."
            )

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
        self._clear_auto_prepare_error(record.id)
        self._schedule_auto_prepare_scan(delay=30, prioritize=record.id)

    def _schedule_auto_prepare_scan(
        self,
        *,
        delay: int = 350,
        prioritize: str = "",
    ) -> None:
        if getattr(self, "_closing", False) or not hasattr(self, "root"):
            return
        if prioritize:
            queue = self._auto_prepare_priority()
            if prioritize not in queue:
                queue.insert(0, prioritize)
        if getattr(self, "_auto_prepare_scan_scheduled", False):
            return
        self._auto_prepare_scan_scheduled = True
        try:
            self.root.after(delay, self._run_auto_prepare_scan)
        except Exception:
            self._auto_prepare_scan_scheduled = False

    def _run_auto_prepare_scan(self) -> None:
        self._auto_prepare_scan_scheduled = False
        if getattr(self, "_closing", False):
            return
        if getattr(self, "_busy", False):
            self._schedule_auto_prepare_scan(delay=800)
            return
        if not self._metadata_ready_for_auto_prepare():
            return

        records = self.store.list_mods()
        self._reconcile_auto_prepare_failures(records)
        by_id = {record.id: record for record in records}
        priority = self._auto_prepare_priority()
        ordered = []
        while priority:
            mod_id = priority.pop(0)
            record = by_id.get(mod_id)
            if record is not None and record not in ordered:
                ordered.append(record)
        ordered.extend(record for record in records if record not in ordered)

        candidate = next(
            (
                record
                for record in ordered
                if self._record_needs_auto_prepare(record)
                and self._auto_prepare_key(record) not in self._auto_prepare_failed_keys()
            ),
            None,
        )
        if candidate is None:
            return

        self._run_task(
            f"Preparing and analyzing {candidate.name} automatically…",
            lambda: LegacyAssetAdapter(
                self.store,
                self.meta_path.get(),
            ).prepare(candidate),
            self._auto_prepare_completed,
            failed=lambda exc: self._auto_prepare_failed(candidate, exc),
        )

    def _auto_prepare_completed(self, prepared) -> None:
        fingerprint = self.metadata_fingerprint.get().strip().casefold()
        if fingerprint and prepared.source_indexed_against.casefold() != fingerprint:
            prepared = replace(prepared, source_indexed_against=fingerprint)
            self.store.save_mod(prepared)
        self._clear_auto_prepare_error(prepared.id)
        self.refresh()
        if self.library.tree.exists(prepared.id):
            self.library.tree.selection_set(prepared.id)
            self.library.tree.see(prepared.id)
            self.show_selected_mod()
        self.status.set(
            f"Ready: {prepared.name} · {len(prepared.files)} game target(s) indexed automatically"
        )
        self._schedule_auto_prepare_scan(delay=80)

    def _auto_prepare_failed(self, record, exc: Exception) -> None:
        key = self._auto_prepare_key(record)
        self._auto_prepare_failed_keys().add(key)
        self._auto_prepare_errors()[record.id] = str(exc)
        self.refresh()
        if self.library.tree.exists(record.id):
            self.library.tree.selection_set(record.id)
            self.library.tree.see(record.id)
            self.show_selected_mod()
        self.status.set(
            f"Could not prepare {record.name} automatically; source preserved and other mods will continue"
        )
        self._schedule_auto_prepare_scan(delay=80)

    def _record_needs_auto_prepare(self, record) -> bool:
        if record.package_type != PACKAGE_UMML_ASSETS:
            return False
        if not self._metadata_ready_for_auto_prepare():
            return False
        fingerprint = self.metadata_fingerprint.get().strip().casefold()
        prepared_against = str(record.prepared_against or "").strip().casefold()
        indexed_against = str(record.source_indexed_against or "").strip().casefold()
        if not record.prepared_path or not record.files:
            return True
        if fingerprint and prepared_against != fingerprint:
            return True
        if fingerprint and indexed_against != fingerprint:
            return True
        if record.option_groups:
            if not record.source_payloads or not record.source_roots:
                return True
            return any(
                source not in record.source_roots
                for source in record.source_payloads
            )
        return False

    def _metadata_ready_for_auto_prepare(self) -> bool:
        try:
            return Path(self.meta_path.get()).expanduser().is_file()
        except (OSError, ValueError):
            return False

    def _auto_prepare_key(self, record) -> tuple[str, str, str, str]:
        return (
            record.id,
            record.version,
            self.metadata_fingerprint.get().strip().casefold(),
            record.source.sha256,
        )

    def _auto_prepare_failed_keys(self) -> set[tuple[str, str, str, str]]:
        value = getattr(self, "_auto_prepare_failures", None)
        if value is None:
            value = set()
            self._auto_prepare_failures = value
        return value

    def _auto_prepare_errors(self) -> dict[str, str]:
        value = getattr(self, "_auto_prepare_error_messages", None)
        if value is None:
            value = {}
            self._auto_prepare_error_messages = value
        return value

    def _auto_prepare_priority(self) -> list[str]:
        value = getattr(self, "_auto_prepare_priority_ids", None)
        if value is None:
            value = []
            self._auto_prepare_priority_ids = value
        return value

    def _clear_auto_prepare_error(self, mod_id: str) -> None:
        self._auto_prepare_errors().pop(mod_id, None)
        self._auto_prepare_failures = {
            key for key in self._auto_prepare_failed_keys() if key[0] != mod_id
        }

    def _reconcile_auto_prepare_failures(self, records) -> None:
        """Drop stale failure labels after a record becomes ready or is removed."""

        pending_ids = {
            record.id
            for record in records
            if self._record_needs_auto_prepare(record)
        }
        errors = self._auto_prepare_errors()
        for mod_id in tuple(errors):
            if mod_id not in pending_ids:
                errors.pop(mod_id, None)
        self._auto_prepare_failures = {
            key
            for key in self._auto_prepare_failed_keys()
            if key[0] in pending_ids
        }


def should_prepare_automatically(record, meta_path: str) -> bool:
    """Import-time policy only; background source indexing has a separate queue."""

    try:
        metadata_ready = Path(meta_path).expanduser().is_file()
    except (OSError, ValueError):
        metadata_ready = False
    return bool(
        record.package_type == PACKAGE_UMML_ASSETS
        and metadata_ready
        and (not record.prepared_path or not record.files)
    )

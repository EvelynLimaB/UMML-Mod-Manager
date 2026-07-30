from __future__ import annotations

from tkinter import filedialog, messagebox, simpledialog

from .deployment import ApplyEngine, LegacyBaselineMigrationRequired
from .legacy_adapter import LegacyAssetAdapter
from .models import PACKAGE_UMML_ASSETS, Profile
from .resolver import Resolution, resolve_profile
from .studio import open_path


class LibraryActions:
    def profile(self) -> Profile:
        name = self.profile_name.get().strip() or "Default"
        for profile in self.store.list_profiles():
            if profile.name == name:
                return profile
        profile = Profile(
            name=name,
            region=self.region.get(),
            installation_key=self.installation_key.get(),
        )
        self.store.save_profile(profile)
        return profile

    def selected_id(self):
        return self.library.selected_id()

    def current_resolution(self) -> Resolution:
        return resolve_profile(
            self.profile(),
            self.store.list_mods(),
            target_region=self.region.get(),
            target_installation_key=self.installation_key.get(),
            metadata_fingerprint=self.metadata_fingerprint.get(),
        )

    def refresh(self):
        selected_before = self.selected_id() if hasattr(self, "library") else None
        profiles = self.store.list_profiles()
        if not profiles:
            self.store.save_profile(
                Profile(
                    "Default",
                    region=self.region.get(),
                    installation_key=self.installation_key.get(),
                )
            )
            profiles = self.store.list_profiles()
        names = [item.name for item in profiles]
        self.library.profile_box.configure(values=names)
        if self.profile_name.get() not in names:
            self.profile_name.set(names[0])
        profile = self.profile()
        self.profile_badge.configure(text=f"Profile: {profile.name}")
        order = {
            mod_id: index + 1
            for index, mod_id in enumerate(profile.enabled)
        }
        needle = self.search_library.get().casefold().strip()
        mods = self.store.list_mods()
        if needle:
            mods = [
                mod
                for mod in mods
                if needle
                in (
                    f"{mod.name} {mod.author} {mod.id} {mod.description} "
                    f"{mod.package_type} {' '.join(mod.regions)}"
                ).casefold()
            ]
        mods.sort(
            key=lambda mod: (
                order.get(mod.id, 10**9),
                mod.name.casefold(),
            )
        )
        tree = self.library.tree
        tree.delete(*tree.get_children())
        for mod in mods:
            tree.insert(
                "",
                "end",
                iid=mod.id,
                text=mod.name,
                values=(
                    order.get(mod.id, "off"),
                    mod.version,
                    mod.source.provider,
                    self._mod_status(mod),
                ),
            )
        if selected_before and tree.exists(selected_before):
            tree.selection_set(selected_before)
            tree.see(selected_before)
            self.show_selected_mod()
        else:
            self.library.clear_details()
        self.status.set(
            f"{len(mods)} mod(s); {len(profile.enabled)} enabled in "
            f"{profile.name}"
        )
        self.refresh_action_states()

    def _mod_status(self, mod) -> str:
        if mod.package_type != PACKAGE_UMML_ASSETS:
            return f"{mod.package_type}; backend needed"
        if not mod.files or not mod.prepared_path:
            return "needs prepare"
        current = self.metadata_fingerprint.get().casefold()
        prepared = str(mod.prepared_against or "").casefold()
        if current and prepared and current != prepared:
            return "stale; re-prepare"
        return "prepared"

    def show_selected_mod(self):
        mod_id = self.selected_id()
        if not mod_id:
            self.library.clear_details()
            self.refresh_action_states()
            return
        try:
            mod = self.store.get_mod(mod_id)
        except Exception as exc:
            self.library.clear_details()
            self.status.set(f"Could not load selected mod: {exc}")
            self.refresh_action_states()
            return
        self.library.mod_title.configure(text=mod.name)
        regions = ", ".join(mod.regions) if mod.regions else "all regions"
        self.library.mod_meta.configure(
            text=(
                f"{mod.author or 'Unknown author'} • {mod.version} • "
                f"{mod.source.provider} • {mod.package_type} • {regions}"
            )
        )
        enabled = mod_id in self.profile().enabled
        self.library.mod_state.configure(
            text=("Enabled" if enabled else "Disabled")
            + " • "
            + self._mod_status(mod)
        )
        details = (
            mod.description
            or "No description was supplied by this package."
        )
        if mod.dependencies:
            details += "\n\nRequires: " + ", ".join(mod.dependencies)
        if mod.incompatibilities:
            details += "\nConflicts with: " + ", ".join(
                mod.incompatibilities
            )
        if mod.prepared_against:
            details += (
                "\nPrepared metadata: "
                + mod.prepared_against
            )
        self.library.set_description(details)
        self.refresh_action_states()

    def new_profile(self):
        name = simpledialog.askstring(
            "New profile",
            "Profile name:",
            parent=self.root,
        )
        if not name or not name.strip():
            return
        name = name.strip()
        existing = {
            profile.name for profile in self.store.list_profiles()
        }
        if name in existing:
            messagebox.showwarning(
                "Profile already exists",
                f"A profile named {name!r} already exists.",
                parent=self.root,
            )
            return
        self.store.save_profile(
            Profile(
                name,
                region=self.region.get(),
                installation_key=self.installation_key.get(),
            )
        )
        self.profile_name.set(name)
        self.save_settings(silent=True)
        self.refresh()

    def _save_profile(self, profile: Profile) -> None:
        self.store.save_profile(profile)

    def rebind_profile(self) -> None:
        installation_key = self.installation_key.get().strip()
        if not installation_key:
            messagebox.showwarning(
                "Verified installation required",
                "Auto-detect the current installation before binding a profile "
                "to it.",
                parent=self.root,
            )
            return

        profile = self.profile()
        region = self.region.get().strip()
        if (
            profile.installation_key == installation_key
            and profile.region == region
        ):
            self.status.set(
                f"{profile.name} is already bound to this installation"
            )
            return

        if (
            profile.installation_key
            and profile.installation_key != installation_key
            and not messagebox.askyesno(
                "Rebind profile?",
                f"{profile.name} is currently bound to "
                f"{profile.installation_key}.\n\nBind it to "
                f"{installation_key} instead?",
                parent=self.root,
            )
        ):
            return

        profile.region = region
        profile.installation_key = installation_key
        self.store.save_profile(profile)
        self.status.set(
            f"Bound {profile.name} to {installation_key}"
        )
        self.refresh()

    def toggle_mod(self):
        mod_id = self.selected_id()
        if not mod_id:
            self.status.set("Select a mod before changing profile membership")
            return
        profile = self.profile()
        profile.enabled = (
            [item for item in profile.enabled if item != mod_id]
            if mod_id in profile.enabled
            else profile.enabled + [mod_id]
        )
        self._save_profile(profile)
        self.refresh()
        if self.library.tree.exists(mod_id):
            self.library.tree.selection_set(mod_id)
            self.show_selected_mod()

    def move_mod(self, delta: int):
        mod_id = self.selected_id()
        profile = self.profile()
        if not mod_id or mod_id not in profile.enabled:
            self.status.set("Enable a selected mod before changing its load order")
            return
        old = profile.enabled.index(mod_id)
        new = max(0, min(len(profile.enabled) - 1, old + delta))
        if new == old:
            self.refresh_action_states()
            return
        profile.enabled.pop(old)
        profile.enabled.insert(new, mod_id)
        self._save_profile(profile)
        self.refresh()
        if self.library.tree.exists(mod_id):
            self.library.tree.selection_set(mod_id)
            self.show_selected_mod()

    def import_folder(self):
        path = filedialog.askdirectory(parent=self.root)
        if path:
            self._import(lambda: self.store.import_folder(path))

    def import_archive(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            filetypes=(
                ("Supported archives", "*.zip *.tar *.tar.gz *.tgz"),
                ("All files", "*"),
            ),
        )
        if path:
            self._import(lambda: self.store.import_archive(path))

    def _import(self, operation):
        self._run_task(
            "Importing mod…",
            operation,
            self._finish_import,
        )

    def _finish_import(self, record):
        self.refresh()
        if self.library.tree.exists(record.id):
            self.library.tree.selection_set(record.id)
            self.library.tree.see(record.id)
            self.show_selected_mod()
        self.status.set(f"Imported {record.name}")
        self.show_page("library")

    def prepare_selected(self):
        mod_id = self.selected_id()
        if not mod_id:
            self.status.set("Select a mod before preparing it")
            return
        record = self.store.get_mod(mod_id)
        if record.package_type != PACKAGE_UMML_ASSETS:
            messagebox.showwarning(
                "Preparation backend unavailable",
                f"{record.name} uses {record.package_type}. The current asset "
                "preparation backend only handles legacy UMML assets.",
                parent=self.root,
            )
            return
        if not self.meta_path.get().strip():
            messagebox.showinfo(
                "Metadata required",
                "Run installation auto-detection in Settings first.",
                parent=self.root,
            )
            return

        def finished(prepared):
            self.refresh()
            if self.library.tree.exists(prepared.id):
                self.library.tree.selection_set(prepared.id)
                self.library.tree.see(prepared.id)
                self.show_selected_mod()
            self.status.set(f"Prepared {len(prepared.files)} asset(s)")

        self._run_task(
            f"Preparing {mod_id}…",
            lambda: LegacyAssetAdapter(
                self.store,
                self.meta_path.get(),
            ).prepare(record),
            finished,
        )

    def create_workspace(self):
        mod_id = self.selected_id()
        if not mod_id:
            self.status.set("Select a mod before creating an editable copy")
            return
        try:
            path = self.store.create_workspace(mod_id)
            open_path(path)
            self.status.set(f"Editable copy created at {path}")
        except Exception as exc:
            messagebox.showerror(
                "Workspace failed",
                str(exc),
                parent=self.root,
            )

    def remove_selected(self):
        mod_id = self.selected_id()
        if not mod_id:
            self.status.set("Select a mod before removing it")
            return
        if any(
            mod_id in profile.enabled
            for profile in self.store.list_profiles()
        ):
            messagebox.showwarning(
                "Mod is enabled",
                "Disable this mod in every profile before removing it.",
                parent=self.root,
            )
            return
        if messagebox.askyesno(
            "Remove mod",
            f"Remove {mod_id} from the manager registry? Preserved source "
            "files are not deleted.",
            parent=self.root,
        ):
            self.store.remove_mod(mod_id)
            self.library.clear_details()
            self.refresh()

    def render_plan(self):
        resolution = self.current_resolution()
        lines = [
            f"PROFILE        {resolution.profile}",
            f"INSTALLATION   "
            f"{resolution.target_installation_key or 'manual/unbound'}",
            f"TARGET REGION  "
            f"{resolution.target_region or 'unspecified'}",
            f"METADATA       "
            f"{resolution.metadata_fingerprint or 'unverified'}",
            f"FILES          {len(resolution.winners)}",
            f"CONFLICTS      {len(resolution.conflicts)}",
            f"BLOCKERS       {len(resolution.blocking_issues)}",
            "",
        ]
        sections = (
            ("Missing mods", resolution.missing),
            ("Needs preparation", resolution.unprepared),
            ("Stale prepared caches", resolution.stale_prepared),
            ("Unsupported packages", resolution.unsupported),
            ("Wrong region", resolution.incompatible),
            ("Wrong installation", resolution.wrong_installation),
            ("Invalid manifests", resolution.invalid),
            ("Missing dependencies", resolution.missing_dependencies),
            (
                "Declared incompatibilities",
                resolution.incompatibility_conflicts,
            ),
            (
                "Duplicate profile entries removed",
                resolution.duplicates,
            ),
        )
        for heading, values in sections:
            if values:
                lines.extend((heading, "-" * len(heading)))
                lines.extend(f"• {value}" for value in values)
                lines.append("")
        if resolution.conflicts:
            lines.extend(("Conflict winners", "=" * 72))
            for conflict in resolution.conflicts:
                lines.append(
                    f"{conflict.path}\n  winner: {conflict.winner}\n"
                    f"  overrides: {', '.join(conflict.overridden)}\n"
                )
        elif not resolution.blocking_issues:
            lines.append("No file conflicts in this profile.")
        self._set_text(self.plan_text, "\n".join(lines))
        self.refresh_action_states()

    def show_plan(self):
        self.show_page("conflicts")

    def apply_profile(self):
        if getattr(self, "_game_running", False):
            messagebox.showwarning(
                "Close the game first",
                "Close Umamusume before applying a profile.",
                parent=self.root,
            )
            return
        if not self.dat_path.get().strip():
            messagebox.showinfo(
                "Game data required",
                "Run installation auto-detection in Settings first.",
                parent=self.root,
            )
            return
        resolution = self.current_resolution()
        if resolution.blocking_issues:
            messagebox.showwarning(
                "Profile is not ready",
                "The profile was not applied. Open Conflicts for the complete "
                f"list of {len(resolution.blocking_issues)} blocking issue(s).",
                parent=self.root,
            )
            self.show_page("conflicts")
            return
        self._run_profile_apply(resolution)

    def _run_profile_apply(
        self,
        resolution: Resolution,
        *,
        import_legacy_baselines: bool = False,
    ):
        operation = lambda: ApplyEngine(
            self.store,
            self.dat_path.get(),
            game_dir=self.game_dir.get() or None,
        ).apply(
            resolution,
            import_legacy_baselines=import_legacy_baselines,
        )

        def finished(result):
            summary = [
                f"Installed files: {result.installed}",
                f"Restored originals: {result.restored}",
                f"Already current: {result.unchanged}",
            ]
            if result.imported_baselines:
                summary.append(
                    "Legacy originals protected: "
                    f"{result.imported_baselines}"
                )
            if result.recovered_transactions:
                summary.append(
                    "Interrupted transactions recovered: "
                    f"{result.recovered_transactions}"
                )
            messagebox.showinfo(
                "Profile applied",
                f"{resolution.profile} is active.\n\n"
                + "\n".join(summary),
                parent=self.root,
            )
            self.status.set(f"Applied {resolution.profile}")
            self.refresh_action_states()

        def failed(exc):
            self._profile_apply_failed(
                resolution,
                exc,
                import_legacy_baselines=import_legacy_baselines,
            )

        self._run_task(
            (
                "Importing legacy originals and applying…"
                if import_legacy_baselines
                else "Applying profile transactionally…"
            ),
            operation,
            finished,
            failed=failed,
        )

    def _profile_apply_failed(
        self,
        resolution: Resolution,
        exc: Exception,
        *,
        import_legacy_baselines: bool,
    ) -> None:
        if not isinstance(exc, LegacyBaselineMigrationRequired):
            self.status.set("Operation failed")
            messagebox.showerror(
                "Operation failed",
                str(exc),
                parent=self.root,
            )
            return

        count = len(exc.paths)
        noun = "file" if count == 1 else "files"
        if exc.can_import and not import_legacy_baselines:
            self.status.set("Legacy originals found")
            should_import = messagebox.askyesno(
                "Finish legacy UMML migration?",
                f"{count} game {noun} belong to an older UMML install. Manager "
                "needs their originals before it can take over safely.\n\n"
                f"The old UMML dat.backup folder contains original copies for "
                f"all {count}. Copy them into Manager's protected baseline and "
                "continue applying?\n\n"
                "The old backups will not be moved or deleted.",
                parent=self.root,
            )
            if should_import:
                self._run_profile_apply(
                    resolution,
                    import_legacy_baselines=True,
                )
            else:
                self.status.set("Apply cancelled")
            return

        usable = len(exc.importable)
        self.status.set("Original files required")
        messagebox.showerror(
            "Original files required",
            f"{count} game {noun} were already modified before UMML Manager "
            "could save their originals, and the old UMML backup folder does "
            f"not contain safe copies for all of them ({usable} of {count} "
            "usable).\n\n"
            "Nothing in the game was changed. Restore the original assets with "
            "legacy UMML or Steam's Verify integrity of game files, then apply "
            "the profile again.",
            parent=self.root,
        )

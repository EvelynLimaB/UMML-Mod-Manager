from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from .models import PACKAGE_UMML_ASSETS
from .process import running_game_processes
from .safety import SafetyError, hash_file, validate_sha256
from .ui_button_actions import ButtonStateActions


class MaintenanceActions(ButtonStateActions):
    """User-facing maintenance status built from verified runtime state."""

    def _mod_status(self, mod) -> str:
        if mod.package_type != PACKAGE_UMML_ASSETS:
            return f"{mod.package_type}; backend needed"
        if not mod.files or not mod.prepared_path:
            return "needs prepare"
        current = self.metadata_fingerprint.get().strip().casefold()
        prepared = str(mod.prepared_against or "").strip().casefold()
        if current and not prepared:
            return "unverified; re-prepare"
        if current and current != prepared:
            return "stale; re-prepare"
        if not current:
            return "prepared; target unverified"
        return "prepared"

    def refresh_action_states(self) -> None:
        super().refresh_action_states()
        if self._closing or self._busy or self._game_running:
            return
        try:
            profile = self.profile()
            resolution = self.current_resolution()
            dat_ready = Path(self.dat_path.get()).expanduser().is_dir()
        except Exception:
            return
        if (
            profile.enabled
            and not self.metadata_fingerprint.get().strip()
            and not resolution.blocking_issues
            and dat_ready
        ):
            self._configure_button(
                self.library.apply_button,
                enabled=False,
                text="Verify metadata to apply",
            )

    def apply_profile(self):
        try:
            profile = self.profile()
            resolution = self.current_resolution()
        except Exception:
            return super().apply_profile()
        if (
            profile.enabled
            and not self.metadata_fingerprint.get().strip()
            and not resolution.blocking_issues
        ):
            messagebox.showinfo(
                "Verified metadata required",
                "Run installation auto-detection in Settings before applying "
                "enabled mods. An empty profile may still restore managed files.",
                parent=self.root,
            )
            self.show_page("settings")
            return
        return super().apply_profile()

    def _manager_diagnostics(self) -> tuple[str, bool]:
        report, ready = super()._manager_diagnostics()
        lines = [report, "", "Target verification:"]

        raw_dat = self.dat_path.get().strip()
        raw_game = self.game_dir.get().strip()
        raw_meta = self.meta_path.get().strip()
        dat = Path(raw_dat).expanduser() if raw_dat else None
        game = Path(raw_game).expanduser() if raw_game else None
        meta = Path(raw_meta).expanduser() if raw_meta else None
        for label, path, expected in (
            ("Game asset data", dat, "directory"),
            ("Game installation", game, "directory"),
            ("Prepared metadata", meta, "file"),
        ):
            exists = bool(
                path
                and (
                    path.is_dir()
                    if expected == "directory"
                    else path.is_file()
                )
            )
            display = str(path) if path is not None else "not set"
            lines.append(
                f"{label}: {'READY' if exists else 'CHECK'} ({display})"
            )
            ready = ready and exists

        recorded = self.metadata_fingerprint.get().strip()
        if meta is not None and meta.is_file() and recorded:
            try:
                expected = validate_sha256(recorded)
                actual = hash_file(meta)
            except (OSError, SafetyError) as exc:
                lines.append(f"Metadata integrity: FAILED ({exc})")
                ready = False
            else:
                if actual == expected:
                    lines.append("Metadata integrity: READY")
                else:
                    lines.append(
                        "Metadata integrity: CHECK (saved fingerprint no longer "
                        "matches the prepared metadata file)"
                    )
                    ready = False
        else:
            lines.append("Metadata integrity: CHECK (no verified fingerprint)")
            ready = False

        try:
            running = running_game_processes(raw_game or None)
        except Exception as exc:
            lines.append(f"Game process inspection: FAILED ({exc})")
            ready = False
        else:
            state = "game running" if running else "game closed"
            lines.append(f"Game process inspection: READY ({state})")

        return "\n".join(lines), ready

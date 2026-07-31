from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable

from .installations import ManagerInstallation, detect_preferred_installation
from .network import tls_diagnostics
from .process import running_game_processes
from .studio import LEGACY_TOOLS, LegacyToolLauncher, open_path
from .ui_theme import SURFACE, TEXT


class SystemActions:
    def launch_legacy_tool(self, tool_id: str):
        tool = next((item for item in LEGACY_TOOLS if item.id == tool_id), None)
        if tool is None:
            messagebox.showerror(
                "Unknown Studio tool",
                f"The requested Studio tool is not registered: {tool_id}",
                parent=self.root,
            )
            return
        if tool.mutating and getattr(self, "_game_running", False):
            messagebox.showwarning(
                "Close the game first",
                f"{tool.name} can change game data. Close Umamusume and try again.",
                parent=self.root,
            )
            return
        try:
            LegacyToolLauncher().launch(
                tool_id,
                dat_path=self.dat_path.get(),
                game_dir=self.game_dir.get(),
                meta_path=self.meta_path.get(),
                region=self.region.get(),
            )
            self.status.set("Opened UMML Studio compatibility host")
        except Exception as exc:
            messagebox.showerror(
                "Could not open legacy tool",
                str(exc),
                parent=self.root,
            )

    def autofill_installation(self, automatic: bool = False):
        """Detect Steam/Proton paths and prepare the readable metadata cache."""

        def completed(installation: ManagerInstallation):
            self.dat_path.set(str(installation.dat_path))
            self.meta_path.set(str(installation.meta_path))
            self.game_dir.set(str(installation.game_dir))
            self.region.set(installation.region)
            self.installation_key.set(installation.key)
            self.metadata_fingerprint.set(
                installation.metadata_fingerprint
            )
            if installation.region in {"global", "japan"}:
                self.gb_region.set(installation.region)
            self.installation_status.set(
                f"Detected {installation.label}. Metadata is ready."
            )
            self._saving_detected_installation = True
            try:
                self.save_settings(silent=True)
            finally:
                self._saving_detected_installation = False
            self.status.set(f"Auto-detected {installation.label}")
            self.refresh()
            self.refresh_action_states()

        def failed(exc: Exception):
            self.installation_status.set(
                "Automatic detection did not complete. Run diagnostics or choose "
                "the paths manually."
            )
            self.status.set("Automatic game detection failed")
            self.refresh_action_states()
            if not automatic:
                messagebox.showerror(
                    "Could not auto-detect Umamusume",
                    str(exc),
                    parent=self.root,
                )

        self._run_task(
            "Detecting Umamusume and preparing metadata…",
            lambda: detect_preferred_installation(self.region.get()),
            completed,
            failed=failed,
        )

    def _mark_manual_installation(self) -> None:
        self.installation_key.set("")
        self.metadata_fingerprint.set("")

    def choose_dat(self):
        path = filedialog.askdirectory(parent=self.root)
        if path:
            chosen = Path(path)
            if (
                chosen.name.casefold() != "dat"
                and (chosen / "dat").is_dir()
            ):
                chosen /= "dat"
            self.dat_path.set(str(chosen))
            self._mark_manual_installation()
            self.installation_status.set(
                "Using manually selected game data. Re-detect to restore a "
                "verified installation identity."
            )
            self.save_settings(silent=True)
            self.refresh_action_states()

    def choose_meta(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            filetypes=(("Database", "*.db meta*"), ("All", "*")),
        )
        if path:
            self.meta_path.set(path)
            self._mark_manual_installation()
            self.installation_status.set(
                "Using manually selected metadata. Re-detect to fingerprint it."
            )
            self.save_settings(silent=True)
            self.refresh()
            self.refresh_action_states()

    def choose_game_dir(self):
        path = filedialog.askdirectory(parent=self.root)
        if path:
            self.game_dir.set(path)
            self._mark_manual_installation()
            self.installation_status.set(
                "Using manually selected game directory. Re-detect to restore "
                "a verified installation identity."
            )
            self.save_settings(silent=True)
            self.refresh_action_states()

    def save_settings(self, silent: bool = False):
        roots = [
            item.strip()
            for item in self.scan_roots.get().split(";")
            if item.strip()
        ]
        try:
            self.store.save_settings(
                {
                    "profile": self.profile_name.get(),
                    "dat_path": self.dat_path.get(),
                    "meta_path": self.meta_path.get(),
                    "game_dir": self.game_dir.get(),
                    "region": self.region.get(),
                    "installation_key": self.installation_key.get(),
                    "metadata_fingerprint": self.metadata_fingerprint.get(),
                    "gamebanana_region": self.gb_region.get(),
                    "scan_roots": roots,
                }
            )
        except Exception as exc:
            if silent:
                self.status.set(f"Could not save settings: {exc}")
                return
            messagebox.showerror(
                "Could not save settings",
                str(exc),
                parent=self.root,
            )
            return
        if not silent:
            self.status.set("Settings saved")
        self.refresh_action_states()

    def open_manager_path(self, name: str):
        allowed = {
            "root",
            "sources",
            "prepared",
            "workspaces",
            "transactions",
        }
        if name not in allowed:
            messagebox.showerror(
                "Unsupported manager path",
                f"The requested manager path is not available: {name}",
                parent=self.root,
            )
            return
        try:
            path = getattr(self.store.paths, name)
            path.mkdir(parents=True, exist_ok=True)
            open_path(path)
        except Exception as exc:
            messagebox.showerror(
                "Could not open folder",
                str(exc),
                parent=self.root,
            )

    def run_diagnostics(self):
        try:
            from .platform_bridge import format_doctor_report

            report, ready = format_doctor_report()
        except Exception as exc:
            report, ready = f"Diagnostics failed:\n{exc}", False

        tls_report, tls_ready = tls_diagnostics()
        manager_report, manager_ready = self._manager_diagnostics()
        report = (
            f"{report}\n\n=== HTTPS TRUST ===\n{tls_report}"
            f"\n\n=== MANAGER STATE ===\n{manager_report}"
        )
        ready = ready and tls_ready and manager_ready

        window = tk.Toplevel(self.root)
        window.title("UMML diagnostics")
        window.geometry("920x620")
        box = tk.Text(
            window,
            wrap="none",
            background=SURFACE,
            foreground=TEXT,
            insertbackground=TEXT,
            font=("TkFixedFont", 10),
        )
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", report)
        box.configure(state="disabled")
        self.status.set(
            "Diagnostics READY"
            if ready
            else "Diagnostics found incomplete setup"
        )

    def _manager_diagnostics(self) -> tuple[str, bool]:
        lines = [f"Data root: {self.store.paths.root}"]
        ready = True
        if self.store.settings_warning:
            lines.append(
                "Settings recovery: CHECK ("
                + self.store.settings_warning
                + ")"
            )
            ready = False
        else:
            lines.append("Settings document: READY")
        try:
            mods = self.store.list_mods()
            profiles = self.store.list_profiles()
            lines.append(f"Mod registry: READY ({len(mods)} records)")
            lines.append(
                f"Profile registry: READY ({len(profiles)} profiles)"
            )
        except Exception as exc:
            lines.append(f"Registry validation: FAILED ({exc})")
            ready = False
        lines.append(
            "Installation identity: "
            + (self.installation_key.get() or "manual/unverified")
        )
        fingerprint = self.metadata_fingerprint.get()
        lines.append(
            "Metadata fingerprint: "
            + (fingerprint if fingerprint else "not recorded")
        )
        pending = []
        if self.store.paths.transactions.is_dir():
            pending = [
                path.name
                for path in self.store.paths.transactions.iterdir()
                if path.is_dir() and path.name.startswith("apply-")
            ]
        if pending:
            lines.append(
                "Interrupted deployment directories: CHECK ("
                + ", ".join(pending[:5])
                + ")"
            )
            ready = False
        else:
            lines.append("Interrupted deployment directories: NONE")
        lines.append(
            "Active deployment state: "
            + (
                "present"
                if self.store.paths.state.is_file()
                else "none"
            )
        )
        return "\n".join(lines), ready

    def _refresh_game_status(self):
        if self._closing:
            return
        try:
            running = running_game_processes(
                self.game_dir.get() or None
            )
            self._game_running = bool(running)
            if running:
                self.game_status.set("Game running")
                self.game_badge.configure(
                    style="Warning.Badge.TLabel"
                )
            else:
                self.game_status.set("Game closed")
                self.game_badge.configure(style="Good.Badge.TLabel")
        except Exception:
            self._game_running = False
            self.game_status.set("Game status unknown")
            self.game_badge.configure(style="Badge.TLabel")
        self.refresh_action_states()
        try:
            self.root.after(5000, self._refresh_game_status)
        except tk.TclError:
            self._closing = True

    def _run_task(
        self,
        label: str,
        operation: Callable[[], Any],
        completed: Callable[[Any], None],
        *,
        failed: Callable[[Exception], None] | None = None,
    ):
        if self._closing:
            return
        if self._busy:
            if failed:
                failed(
                    RuntimeError(
                        "Another UMML operation is still running."
                    )
                )
            else:
                messagebox.showinfo(
                    "UMML is busy",
                    "Another operation is still running.",
                    parent=self.root,
                )
            return
        self._busy = True
        self._task_serial += 1
        task_id = self._task_serial
        self.status.set(label)
        self.progress.start(10)
        self.refresh_action_states()

        def worker():
            try:
                result = operation()
            except Exception as exc:
                self._schedule_task_callback(
                    task_id,
                    lambda error=exc: self._task_failed(
                        error,
                        failed=failed,
                        task_id=task_id,
                    ),
                )
            else:
                self._schedule_task_callback(
                    task_id,
                    lambda value=result: self._task_completed(
                        value,
                        completed,
                        task_id=task_id,
                    ),
                )

        threading.Thread(
            target=worker,
            name=f"umml-manager-task-{task_id}",
            daemon=True,
        ).start()

    def _schedule_task_callback(
        self,
        task_id: int,
        callback: Callable[[], None],
    ) -> None:
        if self._closing or task_id != self._task_serial:
            return
        try:
            self.root.after(0, callback)
        except tk.TclError:
            self._closing = True

    def _task_completed(
        self,
        result: Any,
        completed: Callable[[Any], None],
        *,
        task_id: int,
    ):
        if self._closing or task_id != self._task_serial:
            return
        self._busy = False
        self.progress.stop()
        self.refresh_action_states()
        try:
            completed(result)
        except Exception as exc:
            self._task_failed(exc, task_id=task_id)
        else:
            self.refresh_action_states()

    def _task_failed(
        self,
        exc: Exception,
        *,
        failed: Callable[[Exception], None] | None = None,
        task_id: int | None = None,
    ):
        if self._closing:
            return
        if task_id is not None and task_id != self._task_serial:
            return
        self._busy = False
        self.progress.stop()
        self.refresh_action_states()
        if failed:
            failed(exc)
            self.refresh_action_states()
            return
        self.status.set("Operation failed")
        messagebox.showerror(
            "Operation failed",
            str(exc),
            parent=self.root,
        )

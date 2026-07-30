from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .studio import open_path
from .ui_theme import SURFACE_2, TEXT
from .veterans import (
    UPSTREAM_PROJECT,
    UPSTREAM_URL,
    VeteranDataError,
    VeteranRow,
    VeteranSnapshot,
    VeteranStore,
    filter_rows,
    record_detail,
    roster_summary,
    row_from_record,
)


class VeteransPage(ttk.Frame):
    """Browse validated local snapshots produced by external roster extractors."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.store = VeteranStore(app.store.paths.root / "veterans")
        self.snapshots: dict[str, VeteranSnapshot] = {}
        self.snapshot_labels: dict[str, str] = {}
        self.records: list[dict] = []
        self.rows: list[VeteranRow] = []
        self.visible_rows: list[VeteranRow] = []
        self._search_after: str | None = None
        self._sort_key = "index"
        self._sort_reverse = False

        self.snapshot_value = tk.StringVar()
        self.search_value = tk.StringVar()
        self.summary_value = tk.StringVar(value="No veteran roster imported yet")
        self.notice_value = tk.StringVar(
            value=(
                "Import a data.json produced by UmaExtractor. UMML does not bundle or copy the "
                "extractor because the upstream repository does not declare a license."
            )
        )

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(2, weight=1)

        self._build_toolbar()
        self._build_summary()
        self._build_roster()
        self._build_footer()
        self.search_value.trace_add("write", self._queue_filter)
        self.refresh_snapshots()

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self, padding=(0, 0, 0, 10))
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        toolbar.columnconfigure(4, weight=1)

        ttk.Label(toolbar, text="Snapshot").grid(row=0, column=0, sticky="w", padx=(0, 7))
        self.snapshot_box = ttk.Combobox(
            toolbar,
            textvariable=self.snapshot_value,
            state="readonly",
            width=42,
        )
        self.snapshot_box.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.snapshot_box.bind("<<ComboboxSelected>>", self._snapshot_selected)

        self.import_button = ttk.Button(
            toolbar,
            text="Import data.json",
            style="Accent.TButton",
            command=self.import_json,
        )
        self.import_button.grid(row=0, column=2, padx=(0, 6))
        self.import_latest_button = ttk.Button(
            toolbar,
            text="Import latest output",
            command=self.import_latest_output,
        )
        self.import_latest_button.grid(row=0, column=3, padx=(0, 14))

        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_value)
        self.search_entry.grid(row=0, column=4, sticky="ew", padx=(0, 6))
        self.clear_search_button = ttk.Button(
            toolbar,
            text="Clear",
            command=lambda: self.search_value.set(""),
        )
        self.clear_search_button.grid(row=0, column=5)

        tools = ttk.Frame(self)
        tools.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.choose_extractor_button = ttk.Button(
            tools,
            text="Choose external extractor",
            command=self.choose_extractor,
        )
        self.choose_extractor_button.pack(side="left")
        self.run_extractor_button = ttk.Button(
            tools,
            text="Run external extractor",
            command=self.run_extractor,
        )
        self.run_extractor_button.pack(side="left", padx=(6, 0))
        self.open_upstream_button = ttk.Button(
            tools,
            text="Open UmaExtractor project",
            command=lambda: webbrowser.open(UPSTREAM_URL, new=2),
        )
        self.open_upstream_button.pack(side="left", padx=(6, 0))
        self.open_snapshots_button = ttk.Button(
            tools,
            text="Open roster data",
            command=self.open_roster_data,
        )
        self.open_snapshots_button.pack(side="left", padx=(6, 0))
        self.export_json_button = ttk.Button(
            tools,
            text="Export snapshot",
            command=self.export_snapshot,
        )
        self.export_json_button.pack(side="right")
        self.export_csv_button = ttk.Button(
            tools,
            text="Export filtered CSV",
            command=self.export_csv,
        )
        self.export_csv_button.pack(side="right", padx=(0, 6))

    def _build_summary(self) -> None:
        summary = ttk.Frame(self, style="Surface.TFrame", padding=(14, 10))
        summary.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        summary.columnconfigure(0, weight=1)
        ttk.Label(
            summary,
            textvariable=self.summary_value,
            style="CardTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            summary,
            textvariable=self.notice_value,
            style="SurfaceMuted.TLabel",
            wraplength=1060,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _build_roster(self) -> None:
        self.rowconfigure(3, weight=1)
        left = ttk.Frame(self, style="Surface.TFrame", padding=10)
        left.grid(row=3, column=0, sticky="nsew", padx=(0, 7))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            left,
            columns=("rank", "speed", "stamina", "power", "guts", "wisdom", "factors", "skills"),
            show="tree headings",
            selectmode="browse",
        )
        columns = (
            ("#0", "Veteran", 280, "name"),
            ("rank", "Rank", 80, "rank"),
            ("speed", "Speed", 72, "speed"),
            ("stamina", "Stamina", 78, "stamina"),
            ("power", "Power", 72, "power"),
            ("guts", "Guts", 65, "guts"),
            ("wisdom", "Wisdom", 76, "wisdom"),
            ("factors", "Factors", 72, "factor_count"),
            ("skills", "Skills", 65, "skill_count"),
        )
        for column, label, width, sort_key in columns:
            self.tree.heading(
                column,
                text=label,
                command=lambda key=sort_key: self.sort_rows(key),
            )
            self.tree.column(
                column,
                width=width,
                anchor="w" if column == "#0" else "center",
            )
        scroll_y = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._record_selected)

        details = ttk.Frame(self, style="Surface.TFrame", padding=14)
        details.grid(row=3, column=1, sticky="nsew", padx=(7, 0))
        details.columnconfigure(0, weight=1)
        details.rowconfigure(1, weight=1)
        ttk.Label(details, text="Selected veteran", style="CardTitle.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 8),
        )
        self.detail = tk.Text(
            details,
            wrap="word",
            background=SURFACE_2,
            foreground=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            padx=12,
            pady=12,
            font=("TkFixedFont", 10),
        )
        self.detail.grid(row=1, column=0, sticky="nsew")
        self._set_detail(
            "Import a roster, then select a veteran to inspect stats, factors, skills, "
            "aptitudes, and the original scrubbed record."
        )

    def _build_footer(self) -> None:
        footer = ttk.Frame(self, padding=(0, 10, 0, 0))
        footer.grid(row=4, column=0, columnspan=2, sticky="ew")
        ttk.Label(
            footer,
            text=(
                "Format credit: NECOtype/UmaExtractor, xancia's updated umadump fork, "
                "the original umadump project, and their contributors. No upstream code is bundled."
            ),
            style="Muted.TLabel",
            wraplength=1080,
            justify="left",
        ).pack(side="left", fill="x", expand=True)

    def refresh_snapshots(self, selected_id: str | None = None) -> None:
        try:
            snapshots = self.store.list_snapshots()
        except Exception as exc:
            self.snapshots = {}
            self.snapshot_labels = {}
            self.snapshot_box.configure(values=())
            self.summary_value.set("Veteran snapshot storage could not be read")
            self.notice_value.set(str(exc))
            return

        self.snapshots = {item.id: item for item in snapshots}
        self.snapshot_labels = {self._snapshot_label(item): item.id for item in snapshots}
        labels = list(self.snapshot_labels)
        self.snapshot_box.configure(values=labels)
        if not snapshots:
            self.snapshot_value.set("")
            self.records = []
            self.rows = []
            self.visible_rows = []
            self._render_rows()
            self.summary_value.set("No veteran roster imported yet")
            return

        target_id = selected_id if selected_id in self.snapshots else snapshots[0].id
        target_label = next(label for label, item_id in self.snapshot_labels.items() if item_id == target_id)
        self.snapshot_value.set(target_label)
        self.load_snapshot(target_id)

    def load_snapshot(self, snapshot_id: str) -> None:
        snapshot = self.snapshots.get(snapshot_id)
        if snapshot is None:
            return
        try:
            self.records = self.store.load_records(snapshot)
        except Exception as exc:
            messagebox.showerror("Could not load veteran snapshot", str(exc), parent=self.app.root)
            return
        self.rows = [row_from_record(index, record) for index, record in enumerate(self.records)]
        warning = " ".join(snapshot.warnings)
        self.notice_value.set(
            warning
            or (
                f"Imported from {snapshot.source_name}. Known account identifiers were removed before "
                "the immutable local snapshot was stored."
            )
        )
        self.apply_filter()

    def import_json(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.app.root,
            title="Import UmaExtractor veteran roster",
            filetypes=(("JSON roster", "*.json"), ("All files", "*")),
        )
        if path:
            self._import_path(Path(path))

    def import_latest_output(self) -> None:
        candidates = [
            path
            for path in self.store.inbox.glob("*.json")
            if path.is_file()
        ]
        if not candidates:
            messagebox.showinfo(
                "No extractor output found",
                f"No JSON file exists in the isolated extractor inbox:\n{self.store.inbox}",
                parent=self.app.root,
            )
            return
        latest = max(candidates, key=lambda path: path.stat().st_mtime_ns)
        self._import_path(latest)

    def _import_path(self, path: Path) -> None:
        def completed(snapshot: VeteranSnapshot) -> None:
            self.app.status.set(
                f"Veteran roster ready: {snapshot.record_count:,} record(s)"
            )
            self.refresh_snapshots(snapshot.id)

        def failed(exc: Exception) -> None:
            self.app.status.set("Veteran roster import failed")
            messagebox.showerror("Could not import veteran roster", str(exc), parent=self.app.root)

        self.app._run_task(
            "Validating and importing veteran roster…",
            lambda: self.store.import_json(path),
            completed,
            failed=failed,
        )

    def choose_extractor(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.app.root,
            title="Choose external UmaExtractor executable or script",
            filetypes=(
                ("Extractor", "*.exe *.py"),
                ("Executables", "*.exe"),
                ("Python scripts", "*.py"),
                ("All files", "*"),
            ),
        )
        if not path:
            return
        settings = self.store.load_settings()
        settings["extractor_path"] = str(Path(path).expanduser().resolve())
        self.store.save_settings(settings)
        self.app.status.set(f"External extractor selected: {path}")

    def run_extractor(self) -> None:
        configured = str(self.store.load_settings().get("extractor_path") or "").strip()
        if not configured:
            self.choose_extractor()
            configured = str(self.store.load_settings().get("extractor_path") or "").strip()
            if not configured:
                return
        path = Path(configured).expanduser()
        if not path.is_file():
            messagebox.showerror(
                "External extractor not found",
                f"The configured extractor does not exist:\n{path}",
                parent=self.app.root,
            )
            return

        if os.name != "nt":
            proceed = messagebox.askokcancel(
                "External process permissions",
                "UMML will launch the selected tool without sudo or root privileges. "
                "If its Linux memory reader needs elevation, run it separately and then import data.json.\n\n"
                "Continue?",
                parent=self.app.root,
            )
            if not proceed:
                return

        command = [str(path)]
        if path.suffix.casefold() == ".py":
            command = [sys.executable, str(path)]
        log_path = self.store.inbox / "umaextractor.log"
        try:
            with log_path.open("ab") as log:
                subprocess.Popen(
                    command,
                    cwd=self.store.inbox,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=os.name != "nt",
                )
        except OSError as exc:
            messagebox.showerror("Could not launch external extractor", str(exc), parent=self.app.root)
            return
        self.app.status.set(
            "External UmaExtractor launched. Use its Start Extraction action, then import latest output."
        )

    def open_roster_data(self) -> None:
        try:
            open_path(self.store.root)
        except Exception as exc:
            messagebox.showerror("Could not open roster data", str(exc), parent=self.app.root)

    def export_snapshot(self) -> None:
        snapshot = self._selected_snapshot()
        if snapshot is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.app.root,
            title="Export scrubbed veteran snapshot",
            initialfile=f"veterans-{snapshot.id}.json",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("All files", "*")),
        )
        if not path:
            return
        try:
            self.store.export_snapshot(snapshot, path)
        except Exception as exc:
            messagebox.showerror("Could not export snapshot", str(exc), parent=self.app.root)
            return
        self.app.status.set(f"Exported veteran snapshot to {path}")

    def export_csv(self) -> None:
        if not self.visible_rows:
            self.app.status.set("No filtered veteran records to export")
            return
        path = filedialog.asksaveasfilename(
            parent=self.app.root,
            title="Export filtered veteran table",
            initialfile="veterans-filtered.csv",
            defaultextension=".csv",
            filetypes=(("CSV", "*.csv"), ("All files", "*")),
        )
        if not path:
            return
        records = [self.records[row.index] for row in self.visible_rows]
        try:
            self.store.export_csv(records, path)
        except Exception as exc:
            messagebox.showerror("Could not export CSV", str(exc), parent=self.app.root)
            return
        self.app.status.set(f"Exported {len(records):,} veteran record(s) to {path}")

    def apply_filter(self) -> None:
        self.visible_rows = filter_rows(self.rows, self.search_value.get())
        self._sort_visible_rows()
        self._render_rows()
        summary = roster_summary(self.visible_rows)
        total = len(self.rows)
        shown = summary["count"]
        prefix = f"{shown:,} of {total:,} veterans" if shown != total else f"{total:,} veterans"
        self.summary_value.set(
            f"{prefix} · {summary['unique_characters']:,} character IDs · "
            f"best stat total {summary['best_total']:,} · "
            f"{summary['factors']:,} factors · {summary['skills']:,} skills"
        )

    def sort_rows(self, key: str) -> None:
        if self._sort_key == key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = key
            self._sort_reverse = key not in {"name", "rank", "index"}
        self._sort_visible_rows()
        self._render_rows()

    def _sort_visible_rows(self) -> None:
        key = self._sort_key

        def value(row: VeteranRow):
            if key == "name":
                return row.name.casefold()
            if key == "rank":
                return row.rank.casefold()
            return getattr(row, key, row.index)

        self.visible_rows.sort(key=value, reverse=self._sort_reverse)

    def _render_rows(self) -> None:
        selected = self.tree.selection()
        selected_index = None
        if selected and selected[0].startswith("record-"):
            try:
                selected_index = int(selected[0].removeprefix("record-"))
            except ValueError:
                selected_index = None
        self.tree.delete(*self.tree.get_children())
        for row in self.visible_rows:
            iid = f"record-{row.index}"
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=row.name,
                values=(
                    row.rank,
                    row.speed,
                    row.stamina,
                    row.power,
                    row.guts,
                    row.wisdom,
                    row.factor_count,
                    row.skill_count,
                ),
            )
        if selected_index is not None and self.tree.exists(f"record-{selected_index}"):
            self.tree.selection_set(f"record-{selected_index}")
            self.tree.see(f"record-{selected_index}")
        elif self.visible_rows:
            first = f"record-{self.visible_rows[0].index}"
            self.tree.selection_set(first)
            self.tree.see(first)
            self._record_selected()
        else:
            self._set_detail("No veteran records match the current filter.")

    def _record_selected(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        try:
            index = int(selected[0].removeprefix("record-"))
            record = self.records[index]
        except (ValueError, IndexError):
            return
        row = row_from_record(index, record)
        self._set_detail(record_detail(record, row))

    def _snapshot_selected(self, _event=None) -> None:
        snapshot = self._selected_snapshot()
        if snapshot is not None:
            self.load_snapshot(snapshot.id)

    def _selected_snapshot(self) -> VeteranSnapshot | None:
        snapshot_id = self.snapshot_labels.get(self.snapshot_value.get())
        return self.snapshots.get(snapshot_id or "")

    def _queue_filter(self, *_args) -> None:
        if self._search_after is not None:
            try:
                self.after_cancel(self._search_after)
            except tk.TclError:
                pass
        self._search_after = self.after(180, self._run_queued_filter)

    def _run_queued_filter(self) -> None:
        self._search_after = None
        self.apply_filter()

    def _set_detail(self, value: str) -> None:
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", value)
        self.detail.configure(state="disabled")

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        readonly = "disabled" if busy else "readonly"
        self.snapshot_box.configure(state=readonly)
        self.search_entry.configure(state=state)
        for button in (
            self.import_button,
            self.import_latest_button,
            self.choose_extractor_button,
            self.run_extractor_button,
            self.open_upstream_button,
            self.open_snapshots_button,
            self.export_json_button,
            self.export_csv_button,
            self.clear_search_button,
        ):
            button.configure(state=state)

    @staticmethod
    def _snapshot_label(snapshot: VeteranSnapshot) -> str:
        try:
            imported = datetime.fromisoformat(snapshot.imported_at).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            imported = snapshot.imported_at or snapshot.id
        return f"{imported} · {snapshot.record_count:,} records · {snapshot.source_name}"

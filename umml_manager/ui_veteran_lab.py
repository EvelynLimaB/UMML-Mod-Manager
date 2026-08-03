from __future__ import annotations

import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .ui_veterans import VeteransPage
from .ui_windows import present_toplevel
from .veteran_analysis import (
    aptitude_entries,
    comparison_rows,
    factor_entries,
    factor_quality,
    legacy_sort_key,
    shared_entry_ids,
    skill_entries,
)
from .veterans import VeteranRow, filter_rows, roster_summary, row_from_record


_SORT_LABELS = {
    "total_stats": "Best total stats",
    "legacy": "Legacy strength",
    "speed": "Speed",
    "stamina": "Stamina",
    "power": "Power",
    "guts": "Guts",
    "wisdom": "Wisdom",
    "factor_count": "Factor count",
    "skill_count": "Skill count",
    "name": "Name",
    "index": "Original order",
}
_SORT_KEYS = {label: key for key, label in _SORT_LABELS.items()}


class RosterLabPage(VeteransPage):
    """A readable roster workspace with filtering, comparison, and legacy tools."""

    def __init__(self, parent, app):
        self._colors = _configure_roster_styles(parent)
        self.sort_value = tk.StringVar(master=parent, value=_SORT_LABELS["total_stats"])
        self.filter_three_star = tk.BooleanVar(master=parent, value=False)
        self.filter_has_skills = tk.BooleanVar(master=parent, value=False)
        self.result_count_value = tk.StringVar(master=parent, value="No roster loaded")
        self.tool_hint_value = tk.StringVar(
            master=parent,
            value=(
                "Search any extracted field, or use the visible roster tools to build a shortlist."
            ),
        )
        self.selected_title_value = tk.StringVar(master=parent, value="Select a veteran")
        self.selected_subtitle_value = tk.StringVar(
            master=parent,
            value="Stats, aptitudes, factors, and skills will appear here.",
        )
        self.factor_summary_value = tk.StringVar(master=parent, value="No factors")
        self.skill_summary_value = tk.StringVar(master=parent, value="No skills")
        self.pin_status_value = tk.StringVar(master=parent, value="Nothing pinned")
        self.metric_values = {
            key: tk.StringVar(master=parent, value="0")
            for key in ("veterans", "characters", "best", "factors", "skills")
        }
        self._selected_index: int | None = None
        self._pinned_index: int | None = None
        self._same_character_key: tuple[str, str] | None = None
        self._legacy_mode = False
        self._metrics_columns = 0
        self._layout_after: str | None = None
        super().__init__(parent, app)
        self._sort_key = "total_stats"
        self._sort_reverse = True
        self.bind("<Configure>", self._queue_layout, add="+")
        self.apply_filter()

    def _build_toolbar(self) -> None:
        hero = ttk.Frame(self, style="Roster.Surface.TFrame", padding=(18, 16))
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        hero.columnconfigure(0, weight=1)
        hero.columnconfigure(1, weight=1)

        heading = ttk.Frame(hero, style="Roster.Surface.TFrame")
        heading.grid(row=0, column=0, sticky="nw", padx=(0, 18))
        ttk.Label(
            heading,
            text="Veteran roster",
            style="RosterTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            heading,
            text="Inspect runs, find legacy candidates, and compare parents without reading raw JSON.",
            style="RosterSurfaceMuted.TLabel",
            wraplength=540,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        snapshot = ttk.Frame(hero, style="Roster.Surface.TFrame")
        snapshot.grid(row=0, column=1, sticky="nsew")
        snapshot.columnconfigure(0, weight=1)
        ttk.Label(snapshot, text="Snapshot", style="RosterEyebrow.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.snapshot_box = ttk.Combobox(
            snapshot,
            textvariable=self.snapshot_value,
            state="readonly",
            style="Roster.TCombobox",
        )
        self.snapshot_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.snapshot_box.bind("<<ComboboxSelected>>", self._snapshot_selected)
        self.import_button = ttk.Button(
            snapshot,
            text="Import roster JSON",
            style="RosterAccent.TButton",
            command=self.import_json,
        )
        self.import_button.grid(row=2, column=0, sticky="ew", pady=(8, 0), padx=(0, 4))
        self.import_latest_button = ttk.Button(
            snapshot,
            text="Import latest output",
            style="Roster.TButton",
            command=self.import_latest_output,
        )
        self.import_latest_button.grid(row=2, column=1, sticky="ew", pady=(8, 0), padx=(4, 0))

        source_bar = ttk.Frame(hero, style="Roster.Surface.TFrame")
        source_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ttk.Label(source_bar, text="Data source", style="RosterEyebrow.TLabel").pack(
            side="left", padx=(0, 10)
        )
        self.choose_extractor_button = ttk.Button(
            source_bar,
            text="Install or choose extractor",
            style="Roster.TButton",
            command=self.choose_extractor,
        )
        self.choose_extractor_button.pack(side="left")
        self.run_extractor_button = ttk.Button(
            source_bar,
            text="Run extractor",
            style="Roster.TButton",
            command=self.run_extractor,
        )
        self.run_extractor_button.pack(side="left", padx=(6, 0))
        self.open_upstream_button = ttk.Button(
            source_bar,
            text="Extractor projects",
            style="Roster.TButton",
        )
        self.open_upstream_button.pack(side="left", padx=(6, 0))
        self.open_snapshots_button = ttk.Button(
            source_bar,
            text="Open roster data",
            style="Roster.TButton",
            command=self.open_roster_data,
        )
        self.open_snapshots_button.pack(side="left", padx=(6, 0))
        self.export_json_button = ttk.Button(
            source_bar,
            text="Export snapshot",
            style="Roster.TButton",
            command=self.export_snapshot,
        )
        self.export_json_button.pack(side="right")
        self.export_csv_button = ttk.Button(
            source_bar,
            text="Export filtered CSV",
            style="Roster.TButton",
            command=self.export_csv,
        )
        self.export_csv_button.pack(side="right", padx=(0, 6))

        filters = ttk.Frame(self, style="Roster.Soft.TFrame", padding=(14, 12))
        filters.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        filters.columnconfigure(1, weight=1)
        ttk.Label(filters, text="Search roster", style="RosterSoft.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8)
        )
        self.search_entry = ttk.Entry(
            filters,
            textvariable=self.search_value,
            style="Roster.TEntry",
        )
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(filters, text="Sort", style="RosterSoft.TLabel").grid(
            row=0, column=2, sticky="e", padx=(0, 8)
        )
        self.sort_box = ttk.Combobox(
            filters,
            textvariable=self.sort_value,
            values=tuple(_SORT_KEYS),
            state="readonly",
            width=20,
            style="Roster.TCombobox",
        )
        self.sort_box.grid(row=0, column=3, sticky="ew")
        self.sort_box.bind("<<ComboboxSelected>>", self._sort_selected)

        tools = ttk.Frame(filters, style="Roster.Soft.TFrame")
        tools.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.three_star_check = ttk.Checkbutton(
            tools,
            text="Has a known 3★ factor",
            variable=self.filter_three_star,
            style="Roster.TCheckbutton",
            command=self.apply_filter,
        )
        self.three_star_check.pack(side="left")
        self.has_skills_check = ttk.Checkbutton(
            tools,
            text="Has skills",
            variable=self.filter_has_skills,
            style="Roster.TCheckbutton",
            command=self.apply_filter,
        )
        self.has_skills_check.pack(side="left", padx=(12, 0))
        self.legacy_button = ttk.Button(
            tools,
            text="Build legacy shortlist",
            style="Roster.TButton",
            command=self.toggle_legacy_shortlist,
        )
        self.legacy_button.pack(side="left", padx=(14, 0))
        self.clear_search_button = ttk.Button(
            tools,
            text="Clear filters",
            style="Roster.TButton",
            command=self.clear_filters,
        )
        self.clear_search_button.pack(side="right")

    def _build_summary(self) -> None:
        self.rowconfigure(2, weight=0)
        summary = ttk.Frame(self, style="Roster.TFrame")
        summary.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        summary.columnconfigure(0, weight=1)
        self.metrics = ttk.Frame(summary, style="Roster.TFrame")
        self.metrics.grid(row=0, column=0, sticky="ew")
        metric_specs = (
            ("veterans", "Veterans"),
            ("characters", "Characters"),
            ("best", "Best total"),
            ("factors", "Factors"),
            ("skills", "Skills"),
        )
        self.metric_cards: list[ttk.Frame] = []
        for key, label in metric_specs:
            card = ttk.Frame(
                self.metrics,
                style="Roster.Surface.TFrame",
                padding=(14, 10),
            )
            ttk.Label(
                card,
                textvariable=self.metric_values[key],
                style="RosterMetricValue.TLabel",
            ).pack(anchor="w")
            ttk.Label(card, text=label, style="RosterSurfaceMuted.TLabel").pack(
                anchor="w", pady=(2, 0)
            )
            self.metric_cards.append(card)
        ttk.Label(
            summary,
            textvariable=self.summary_value,
            style="RosterMuted.TLabel",
            justify="left",
            wraplength=1120,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(
            summary,
            textvariable=self.tool_hint_value,
            style="RosterHint.TLabel",
            justify="left",
            wraplength=1120,
        ).grid(row=2, column=0, sticky="w", pady=(3, 0))
        self._layout_metrics(1200)

    def _build_roster(self) -> None:
        self.rowconfigure(3, weight=1)
        main = ttk.Panedwindow(self, orient="horizontal")
        main.grid(row=3, column=0, columnspan=2, sticky="nsew")

        left = ttk.Frame(main, style="Roster.Surface.TFrame", padding=(12, 12))
        right = ttk.Frame(main, style="Roster.Surface.TFrame", padding=(14, 12))
        main.add(left, weight=3)
        main.add(right, weight=2)

        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)
        left_header = ttk.Frame(left, style="Roster.Surface.TFrame")
        left_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        left_header.columnconfigure(0, weight=1)
        ttk.Label(
            left_header,
            text="Roster",
            style="RosterSectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            left_header,
            textvariable=self.result_count_value,
            style="RosterSurfaceMuted.TLabel",
        ).grid(row=0, column=1, sticky="e")

        self.tree = ttk.Treeview(
            left,
            columns=("rank", "total", "speed", "stamina", "power", "factors", "skills"),
            show="tree headings",
            selectmode="browse",
            style="Roster.Treeview",
        )
        columns = (
            ("#0", "Veteran", 195, "name", "w", True),
            ("rank", "Rank", 56, "rank", "center", False),
            ("total", "Total", 68, "total_stats", "center", False),
            ("speed", "Spd", 58, "speed", "center", False),
            ("stamina", "Sta", 58, "stamina", "center", False),
            ("power", "Pow", 58, "power", "center", False),
            ("factors", "Factors", 76, "factor_count", "center", False),
            ("skills", "Skills", 58, "skill_count", "center", False),
        )
        for column, label, width, sort_key, anchor, stretch in columns:
            self.tree.heading(
                column,
                text=label,
                command=lambda key=sort_key: self.sort_rows(key),
            )
            self.tree.column(
                column,
                width=width,
                minwidth=48,
                anchor=anchor,
                stretch=stretch,
            )
        scroll_y = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        scroll_y.grid(row=1, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self._record_selected)
        self.tree.bind("<Double-1>", lambda _event: self.pin_selected())
        self.tree.tag_configure(
            "pinned",
            background=self._colors["accent_soft"],
            foreground=self._colors["text"],
        )

        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        ttk.Label(
            right,
            textvariable=self.selected_title_value,
            style="RosterSectionTitle.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            right,
            textvariable=self.selected_subtitle_value,
            style="RosterSurfaceMuted.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 8))

        action_bar = ttk.Frame(right, style="Roster.Surface.TFrame")
        action_bar.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        action_bar.columnconfigure(0, weight=1)
        action_bar.columnconfigure(1, weight=1)
        self.pin_button = ttk.Button(
            action_bar,
            text="Pin for compare",
            style="Roster.TButton",
            command=self.pin_selected,
        )
        self.pin_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.compare_button = ttk.Button(
            action_bar,
            text="Compare with pinned",
            style="Roster.TButton",
            command=self.compare_selected,
        )
        self.compare_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.same_character_button = ttk.Button(
            action_bar,
            text="Only this character",
            style="Roster.TButton",
            command=self.toggle_same_character,
        )
        self.same_character_button.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=(6, 0))
        self.export_selected_button = ttk.Button(
            action_bar,
            text="Export selected",
            style="Roster.TButton",
            command=self.export_selected,
        )
        self.export_selected_button.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))
        self.copy_ids_button = ttk.Button(
            action_bar,
            text="Copy IDs",
            style="Roster.TButton",
            command=self.copy_selected_ids,
        )
        self.copy_ids_button.grid(row=2, column=0, sticky="ew", padx=(0, 4), pady=(6, 0))
        ttk.Label(
            action_bar,
            textvariable=self.pin_status_value,
            style="RosterSurfaceMuted.TLabel",
            anchor="center",
        ).grid(row=2, column=1, sticky="ew", padx=(4, 0), pady=(6, 0))

        self.detail_notebook = ttk.Notebook(right, style="Roster.TNotebook")
        self.detail_notebook.grid(row=3, column=0, sticky="nsew")
        self.overview_tab = ttk.Frame(
            self.detail_notebook,
            style="Roster.Soft.TFrame",
            padding=(12, 12),
        )
        self.factor_tab = ttk.Frame(
            self.detail_notebook,
            style="Roster.Soft.TFrame",
            padding=(10, 10),
        )
        self.skill_tab = ttk.Frame(
            self.detail_notebook,
            style="Roster.Soft.TFrame",
            padding=(10, 10),
        )
        self.raw_tab = ttk.Frame(
            self.detail_notebook,
            style="Roster.Soft.TFrame",
            padding=(8, 8),
        )
        self.detail_notebook.add(self.overview_tab, text="Overview")
        self.detail_notebook.add(self.factor_tab, text="Factors")
        self.detail_notebook.add(self.skill_tab, text="Skills")
        self.detail_notebook.add(self.raw_tab, text="Raw")
        self._build_overview_tab()
        self.factor_tree = self._build_entry_tab(
            self.factor_tab,
            self.factor_summary_value,
        )
        self.skill_tree = self._build_entry_tab(
            self.skill_tab,
            self.skill_summary_value,
        )
        self._build_raw_tab()
        self._set_detail(
            "Import a roster, then select a veteran. The overview replaces the old wall of raw text; "
            "the Raw tab remains available when you actually need it."
        )

    def _build_overview_tab(self) -> None:
        tab = self.overview_tab
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(7, weight=1)
        ttk.Label(tab, text="Stats", style="RosterSoftSection.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        self.stat_widgets: dict[str, tuple[ttk.Progressbar, tk.StringVar]] = {}
        for row_index, (key, label) in enumerate(
            (
                ("speed", "Speed"),
                ("stamina", "Stamina"),
                ("power", "Power"),
                ("guts", "Guts"),
                ("wisdom", "Wisdom"),
            ),
            start=1,
        ):
            value = tk.StringVar(master=tab, value="0")
            ttk.Label(tab, text=label, style="RosterSoft.TLabel", width=9).grid(
                row=row_index, column=0, sticky="w", pady=3
            )
            bar = ttk.Progressbar(
                tab,
                orient="horizontal",
                mode="determinate",
                maximum=2000,
                style="Roster.Horizontal.TProgressbar",
            )
            bar.grid(row=row_index, column=1, sticky="ew", padx=(6, 8), pady=3)
            ttk.Label(
                tab,
                textvariable=value,
                style="RosterSoftValue.TLabel",
                width=5,
                anchor="e",
            ).grid(row=row_index, column=2, sticky="e", pady=3)
            self.stat_widgets[key] = (bar, value)

        self.total_stats_value = tk.StringVar(master=tab, value="Total 0")
        ttk.Label(
            tab,
            textvariable=self.total_stats_value,
            style="RosterSoftSection.TLabel",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 8))
        ttk.Separator(tab).grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(tab, text="Aptitudes", style="RosterSoftSection.TLabel").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        self.aptitude_tree = ttk.Treeview(
            tab,
            columns=("value",),
            show="tree headings",
            height=7,
            style="Roster.Compact.Treeview",
        )
        self.aptitude_tree.heading("#0", text="Aptitude")
        self.aptitude_tree.heading("value", text="Value")
        self.aptitude_tree.column("#0", width=190, stretch=True)
        self.aptitude_tree.column("value", width=70, anchor="center", stretch=False)
        self.aptitude_tree.grid(row=9, column=0, columnspan=3, sticky="nsew")
        tab.rowconfigure(9, weight=1)

    def _build_entry_tab(self, tab: ttk.Frame, summary_var: tk.StringVar) -> ttk.Treeview:
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        ttk.Label(
            tab,
            textvariable=summary_var,
            style="RosterSoftSection.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 7))
        tree = ttk.Treeview(
            tab,
            columns=("id", "level"),
            show="tree headings",
            style="Roster.Compact.Treeview",
        )
        tree.heading("#0", text="Name")
        tree.heading("id", text="ID")
        tree.heading("level", text="Level")
        tree.column("#0", width=210, stretch=True)
        tree.column("id", width=92, anchor="center", stretch=False)
        tree.column("level", width=62, anchor="center", stretch=False)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=1, column=0, sticky="nsew")
        scroll.grid(row=1, column=1, sticky="ns")
        return tree

    def _build_raw_tab(self) -> None:
        self.raw_tab.columnconfigure(0, weight=1)
        self.raw_tab.rowconfigure(0, weight=1)
        self.raw_text = tk.Text(
            self.raw_tab,
            wrap="none",
            background=self._colors["soft"],
            foreground=self._colors["text"],
            insertbackground=self._colors["text"],
            selectbackground=self._colors["accent"],
            selectforeground=self._colors["selection_text"],
            relief="flat",
            borderwidth=0,
            padx=10,
            pady=10,
            font=("TkFixedFont", 9),
        )
        scroll_y = ttk.Scrollbar(self.raw_tab, orient="vertical", command=self.raw_text.yview)
        scroll_x = ttk.Scrollbar(self.raw_tab, orient="horizontal", command=self.raw_text.xview)
        self.raw_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self.raw_text.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

    def _build_footer(self) -> None:
        footer = ttk.Frame(self, style="Roster.TFrame", padding=(0, 8, 0, 0))
        footer.grid(row=4, column=0, columnspan=2, sticky="ew")
        ttk.Label(
            footer,
            text=(
                "Local, scrubbed snapshots. Format credit: NECOtype/UmaExtractor, "
                "xancia's fork, Werseter/umadump, rockisch/umadump, and contributors."
            ),
            style="RosterMuted.TLabel",
            wraplength=1160,
            justify="left",
        ).pack(side="left", fill="x", expand=True)

    def apply_filter(self) -> None:
        values = filter_rows(self.rows, self.search_value.get())
        filtered: list[VeteranRow] = []
        for row in values:
            record = self.records[row.index]
            quality = factor_quality(record)
            if self.filter_three_star.get() and quality.three_star_count < 1:
                continue
            if self.filter_has_skills.get() and row.skill_count < 1:
                continue
            if self._legacy_mode and row.factor_count < 1:
                continue
            if self._same_character_key is not None:
                field, expected = self._same_character_key
                actual = row.chara_id if field == "chara_id" else row.card_id
                if actual != expected:
                    continue
            filtered.append(row)

        self.visible_rows = filtered
        self._sort_visible_rows()
        self._render_rows()
        summary = roster_summary(self.visible_rows)
        shown = summary["count"]
        total = len(self.rows)
        self.result_count_value.set(
            f"{shown:,} shown" if shown != total else f"{total:,} total"
        )
        self.metric_values["veterans"].set(f"{shown:,}")
        self.metric_values["characters"].set(f"{summary['unique_characters']:,}")
        self.metric_values["best"].set(f"{summary['best_total']:,}")
        self.metric_values["factors"].set(f"{summary['factors']:,}")
        self.metric_values["skills"].set(f"{summary['skills']:,}")
        prefix = f"Showing {shown:,} of {total:,}" if shown != total else f"{total:,} veterans"
        self.summary_value.set(
            f"{prefix} · {summary['unique_characters']:,} character IDs · "
            f"best total {summary['best_total']:,}."
        )
        if self._legacy_mode:
            self.tool_hint_value.set(
                "Legacy shortlist is a transparent heuristic: known 3★ factors, known star total, "
                "factor count, then total stats. It does not invent compatibility from missing master data."
            )
        elif self._same_character_key is not None:
            self.tool_hint_value.set(
                f"Character filter active: {self._same_character_key[1]}. Clear filters to return to the full roster."
            )
        else:
            self.tool_hint_value.set(
                "Double-click a row to pin it, select another veteran, then use Compare with pinned."
            )

    def sort_rows(self, key: str) -> None:
        if self._sort_key == key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = key
            self._sort_reverse = key not in {"name", "rank", "index"}
        self.sort_value.set(_SORT_LABELS.get(key, _SORT_LABELS["total_stats"]))
        self._sort_visible_rows()
        self._render_rows()

    def _sort_selected(self, _event=None) -> None:
        key = _SORT_KEYS.get(self.sort_value.get(), "total_stats")
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
            if key == "legacy":
                return legacy_sort_key(self.records[row.index], row.total_stats)
            if key == "total_stats":
                return row.total_stats
            return getattr(row, key, row.index)

        self.visible_rows.sort(key=value, reverse=self._sort_reverse)

    def _render_rows(self) -> None:
        selected_index = self._selected_tree_index()
        self.tree.delete(*self.tree.get_children())
        for row in self.visible_rows:
            quality = factor_quality(self.records[row.index])
            factor_label = str(row.factor_count)
            if quality.known_levels:
                factor_label = f"{row.factor_count} · {quality.total_stars}★"
            tags = ("pinned",) if row.index == self._pinned_index else ()
            self.tree.insert(
                "",
                "end",
                iid=f"record-{row.index}",
                text=row.name,
                values=(
                    row.rank,
                    row.total_stats,
                    row.speed,
                    row.stamina,
                    row.power,
                    factor_label,
                    row.skill_count,
                ),
                tags=tags,
            )
        target = selected_index
        if target is None or not self.tree.exists(f"record-{target}"):
            target = self.visible_rows[0].index if self.visible_rows else None
        if target is not None:
            iid = f"record-{target}"
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)
            self._record_selected()
        else:
            self._selected_index = None
            self._set_detail("No veteran records match the current filters.")

    def _record_selected(self, _event=None) -> None:
        index = self._selected_tree_index()
        if index is None or index >= len(self.records):
            return
        self._selected_index = index
        record = self.records[index]
        row = row_from_record(index, record)
        self.selected_title_value.set(row.name)
        identity = [
            f"Card {row.card_id}" if row.card_id else "",
            f"Character {row.chara_id}" if row.chara_id else "",
            f"Veteran {row.trained_chara_id}" if row.trained_chara_id else "",
            f"Rank {row.rank}" if row.rank != "—" else "",
        ]
        self.selected_subtitle_value.set(" · ".join(item for item in identity if item))

        maximum = max(2000, int(math.ceil(max(row.speed, row.stamina, row.power, row.guts, row.wisdom, 1) / 500) * 500))
        for key in ("speed", "stamina", "power", "guts", "wisdom"):
            bar, value = self.stat_widgets[key]
            stat = int(getattr(row, key))
            bar.configure(maximum=maximum, value=stat)
            value.set(f"{stat:,}")
        self.total_stats_value.set(f"Total stats  {row.total_stats:,}")

        self._replace_tree(
            self.aptitude_tree,
            ((label, value) for label, value in aptitude_entries(record)),
            value_count=1,
        )
        factors = factor_entries(record)
        skills = skill_entries(record)
        self._replace_entry_tree(self.factor_tree, factors)
        self._replace_entry_tree(self.skill_tree, skills)
        quality = factor_quality(record)
        self.factor_summary_value.set(quality.summary)
        self.skill_summary_value.set(f"{len(skills)} skill(s)")
        self.detail_notebook.tab(self.factor_tab, text=f"Factors ({len(factors)})")
        self.detail_notebook.tab(self.skill_tab, text=f"Skills ({len(skills)})")
        self._set_raw(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False))

        self.pin_button.configure(
            state="normal",
            text="Pinned" if index == self._pinned_index else "Pin for compare",
            style="RosterActive.TButton" if index == self._pinned_index else "Roster.TButton",
        )
        compare_ready = self._pinned_index is not None and self._pinned_index != index
        self.compare_button.configure(state="normal" if compare_ready else "disabled")
        self.same_character_button.configure(state="normal")
        self.export_selected_button.configure(state="normal")
        self.copy_ids_button.configure(state="normal")

    def _set_detail(self, value: str) -> None:
        self.selected_title_value.set("Select a veteran")
        self.selected_subtitle_value.set(value)
        for bar, variable in getattr(self, "stat_widgets", {}).values():
            bar.configure(value=0)
            variable.set("0")
        if hasattr(self, "total_stats_value"):
            self.total_stats_value.set("Total stats  0")
        for tree_name in ("aptitude_tree", "factor_tree", "skill_tree"):
            tree = getattr(self, tree_name, None)
            if tree is not None:
                tree.delete(*tree.get_children())
        self.factor_summary_value.set("No factors")
        self.skill_summary_value.set("No skills")
        if hasattr(self, "raw_text"):
            self._set_raw(value)
        for button_name in (
            "pin_button",
            "compare_button",
            "same_character_button",
            "export_selected_button",
            "copy_ids_button",
        ):
            button = getattr(self, button_name, None)
            if button is not None:
                button.configure(state="disabled")

    def toggle_legacy_shortlist(self) -> None:
        self._legacy_mode = not self._legacy_mode
        if self._legacy_mode:
            self._sort_key = "legacy"
            self._sort_reverse = True
            self.sort_value.set(_SORT_LABELS["legacy"])
            self.legacy_button.configure(
                text="Legacy shortlist active",
                style="RosterActive.TButton",
            )
        else:
            self._sort_key = "total_stats"
            self._sort_reverse = True
            self.sort_value.set(_SORT_LABELS["total_stats"])
            self.legacy_button.configure(
                text="Build legacy shortlist",
                style="Roster.TButton",
            )
        self.apply_filter()

    def clear_filters(self) -> None:
        self.search_value.set("")
        self.filter_three_star.set(False)
        self.filter_has_skills.set(False)
        self._same_character_key = None
        self._legacy_mode = False
        self._sort_key = "total_stats"
        self._sort_reverse = True
        self.sort_value.set(_SORT_LABELS["total_stats"])
        self.legacy_button.configure(
            text="Build legacy shortlist",
            style="Roster.TButton",
        )
        self.same_character_button.configure(text="Only this character")
        self.apply_filter()

    def toggle_same_character(self) -> None:
        if self._same_character_key is not None:
            self._same_character_key = None
            self.same_character_button.configure(text="Only this character")
            self.apply_filter()
            return
        if self._selected_index is None:
            return
        row = row_from_record(self._selected_index, self.records[self._selected_index])
        if row.chara_id:
            self._same_character_key = ("chara_id", row.chara_id)
        elif row.card_id:
            self._same_character_key = ("card_id", row.card_id)
        else:
            self.app.status.set("Selected veteran has no character or card ID to filter")
            return
        self.same_character_button.configure(text="Show all characters")
        self.apply_filter()

    def pin_selected(self) -> None:
        if self._selected_index is None:
            return
        self._pinned_index = self._selected_index
        row = row_from_record(self._pinned_index, self.records[self._pinned_index])
        self.pin_status_value.set(f"Pinned: {row.name}")
        self._render_rows()

    def compare_selected(self) -> None:
        if (
            self._pinned_index is None
            or self._selected_index is None
            or self._pinned_index == self._selected_index
        ):
            return
        left_record = self.records[self._pinned_index]
        right_record = self.records[self._selected_index]
        left_row = row_from_record(self._pinned_index, left_record)
        right_row = row_from_record(self._selected_index, right_record)

        window = tk.Toplevel(self.winfo_toplevel())
        window.title("Uma Mod Manager · Compare veterans")
        window.geometry("900x620")
        window.minsize(760, 520)
        window.configure(background=self._colors["bg"])
        window.columnconfigure(0, weight=1)
        window.rowconfigure(2, weight=1)

        header = ttk.Frame(window, style="Roster.TFrame", padding=(18, 16))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Veteran comparison", style="RosterTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Pinned veteran is on the left. Positive deltas favor the current selection.",
            style="RosterMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        identities = ttk.Frame(window, style="Roster.TFrame", padding=(18, 0, 18, 10))
        identities.grid(row=1, column=0, sticky="ew")
        identities.columnconfigure(0, weight=1)
        identities.columnconfigure(1, weight=1)
        for column, title, row, caption in (
            (0, "Pinned", left_row, left_row.name),
            (1, "Current", right_row, right_row.name),
        ):
            card = ttk.Frame(
                identities,
                style="Roster.Surface.TFrame",
                padding=(14, 10),
            )
            card.grid(row=0, column=column, sticky="ew", padx=(0, 5) if column == 0 else (5, 0))
            ttk.Label(card, text=title, style="RosterEyebrow.TLabel").pack(anchor="w")
            ttk.Label(
                card,
                text=caption,
                style="RosterSectionTitle.TLabel",
                wraplength=340,
                justify="left",
            ).pack(anchor="w", pady=(3, 0))
            ttk.Label(
                card,
                text=f"Card {row.card_id or 'unknown'} · Veteran {row.trained_chara_id or 'unknown'}",
                style="RosterSurfaceMuted.TLabel",
            ).pack(anchor="w", pady=(3, 0))

        content = ttk.Frame(window, style="Roster.TFrame", padding=(18, 0, 18, 16))
        content.grid(row=2, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        comparison = ttk.Treeview(
            content,
            columns=("left", "delta", "right"),
            show="tree headings",
            style="Roster.Treeview",
        )
        comparison.heading("#0", text="Metric")
        comparison.heading("left", text="Pinned")
        comparison.heading("delta", text="Δ")
        comparison.heading("right", text="Current")
        comparison.column("#0", width=180, stretch=True)
        comparison.column("left", width=110, anchor="center", stretch=False)
        comparison.column("delta", width=90, anchor="center", stretch=False)
        comparison.column("right", width=110, anchor="center", stretch=False)
        for metric, left_value, delta, right_value in comparison_rows(left_row, right_row):
            comparison.insert(
                "",
                "end",
                text=metric,
                values=(f"{left_value:,}", f"{delta:+,}", f"{right_value:,}"),
            )
        comparison.grid(row=0, column=0, sticky="nsew")

        overlap = ttk.Frame(content, style="Roster.Soft.TFrame", padding=(12, 10))
        overlap.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        overlap.columnconfigure(0, weight=1)
        shared_factors = shared_entry_ids(factor_entries(left_record), factor_entries(right_record))
        shared_skills = shared_entry_ids(skill_entries(left_record), skill_entries(right_record))
        ttk.Label(
            overlap,
            text=f"Shared factors: {', '.join(shared_factors) if shared_factors else 'none detected'}",
            style="RosterSoft.TLabel",
            wraplength=800,
            justify="left",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            overlap,
            text=f"Shared skills: {', '.join(shared_skills) if shared_skills else 'none detected'}",
            style="RosterSoft.TLabel",
            wraplength=800,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        window.bind("<Escape>", lambda _event: window.destroy())
        present_toplevel(window, self.winfo_toplevel())

    def export_selected(self) -> None:
        if self._selected_index is None:
            return
        row = row_from_record(self._selected_index, self.records[self._selected_index])
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title="Export selected veteran",
            initialfile=f"veteran-{row.trained_chara_id or self._selected_index + 1}.json",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("All files", "*")),
        )
        if not path:
            return
        snapshot = self._selected_snapshot()
        payload: dict[str, Any] = {
            "snapshot_id": snapshot.id if snapshot is not None else "",
            "source_name": snapshot.source_name if snapshot is not None else "",
            "record": self.records[self._selected_index],
        }
        try:
            Path(path).write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            messagebox.showerror("Could not export veteran", str(exc), parent=self.winfo_toplevel())
            return
        self.app.status.set(f"Exported selected veteran to {path}")

    def copy_selected_ids(self) -> None:
        if self._selected_index is None:
            return
        row = row_from_record(self._selected_index, self.records[self._selected_index])
        value = "\n".join(
            (
                f"chara_id={row.chara_id or ''}",
                f"card_id={row.card_id or ''}",
                f"trained_chara_id={row.trained_chara_id or ''}",
            )
        )
        root = self.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(value)
        self.app.status.set("Copied selected veteran IDs")

    def set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        readonly = "disabled" if busy else "readonly"
        self.snapshot_box.configure(state=readonly)
        self.search_entry.configure(state=state)
        self.sort_box.configure(state=readonly)
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
            self.legacy_button,
            self.three_star_check,
            self.has_skills_check,
        ):
            button.configure(state=state)
        if not busy:
            self._record_selected()

    def _selected_tree_index(self) -> int | None:
        selected = self.tree.selection()
        if not selected or not selected[0].startswith("record-"):
            return None
        try:
            return int(selected[0].removeprefix("record-"))
        except ValueError:
            return None

    @staticmethod
    def _replace_tree(tree: ttk.Treeview, rows, *, value_count: int) -> None:
        tree.delete(*tree.get_children())
        for index, row in enumerate(rows):
            values = tuple(row[1 : 1 + value_count])
            tree.insert("", "end", iid=f"item-{index}", text=row[0], values=values)

    @staticmethod
    def _replace_entry_tree(tree: ttk.Treeview, entries) -> None:
        tree.delete(*tree.get_children())
        for index, entry in enumerate(entries):
            tree.insert(
                "",
                "end",
                iid=f"entry-{index}",
                text=entry.name,
                values=(entry.id, entry.level_label),
            )

    def _set_raw(self, value: str) -> None:
        self.raw_text.configure(state="normal")
        self.raw_text.delete("1.0", "end")
        self.raw_text.insert("1.0", value)
        self.raw_text.configure(state="disabled")

    def _queue_layout(self, event) -> None:
        if event.widget is not self:
            return
        if self._layout_after is not None:
            try:
                self.after_cancel(self._layout_after)
            except tk.TclError:
                pass
        self._layout_after = self.after(40, lambda: self._layout_metrics(event.width))

    def _layout_metrics(self, width: int) -> None:
        self._layout_after = None
        columns = 3 if width < 1080 else 5
        if columns == self._metrics_columns:
            return
        self._metrics_columns = columns
        for card in self.metric_cards:
            card.grid_forget()
        for column in range(columns):
            self.metrics.columnconfigure(column, weight=1, uniform="roster-metric")
        for index, card in enumerate(self.metric_cards):
            row, column = divmod(index, columns)
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 4, 0 if column == columns - 1 else 4),
                pady=(0 if row == 0 else 8, 0),
            )


def _configure_roster_styles(widget: tk.Misc) -> dict[str, str]:
    style = ttk.Style(widget)
    background = str(style.lookup("TFrame", "background") or "#1b1b1f")
    dark = _is_dark(background)
    if dark:
        colors = {
            "bg": "#1b1b1f",
            "surface": "#202127",
            "soft": "#282930",
            "hover": "#30323a",
            "text": "#f4f4f5",
            "muted": "#a9acb6",
            "border": "#3a3c45",
            "accent": "#6a9e3a",
            "accent_hover": "#7aba40",
            "accent_soft": "#293823",
            "selection_text": "#ffffff",
        }
    else:
        colors = {
            "bg": "#f2f3f7",
            "surface": "#ffffff",
            "soft": "#eef0f6",
            "hover": "#e3e6ed",
            "text": "#2b2f38",
            "muted": "#626b79",
            "border": "#d6dae3",
            "accent": "#3f8a00",
            "accent_hover": "#347300",
            "accent_soft": "#e4f0d9",
            "selection_text": "#ffffff",
        }

    style.configure("Roster.TFrame", background=colors["bg"])
    style.configure("Roster.Surface.TFrame", background=colors["surface"])
    style.configure("Roster.Soft.TFrame", background=colors["soft"])
    style.configure("Roster.TLabel", background=colors["bg"], foreground=colors["text"])
    style.configure(
        "RosterMuted.TLabel",
        background=colors["bg"],
        foreground=colors["muted"],
    )
    style.configure(
        "RosterHint.TLabel",
        background=colors["bg"],
        foreground=colors["accent"],
        font=("TkDefaultFont", 9, "bold"),
    )
    style.configure(
        "RosterSurfaceMuted.TLabel",
        background=colors["surface"],
        foreground=colors["muted"],
    )
    style.configure(
        "RosterSoft.TLabel",
        background=colors["soft"],
        foreground=colors["text"],
    )
    style.configure(
        "RosterTitle.TLabel",
        background=colors["surface"],
        foreground=colors["text"],
        font=("TkDefaultFont", 20, "bold"),
    )
    style.configure(
        "RosterSectionTitle.TLabel",
        background=colors["surface"],
        foreground=colors["text"],
        font=("TkDefaultFont", 12, "bold"),
    )
    style.configure(
        "RosterSoftSection.TLabel",
        background=colors["soft"],
        foreground=colors["text"],
        font=("TkDefaultFont", 10, "bold"),
    )
    style.configure(
        "RosterSoftValue.TLabel",
        background=colors["soft"],
        foreground=colors["text"],
        font=("TkDefaultFont", 10, "bold"),
    )
    style.configure(
        "RosterEyebrow.TLabel",
        background=colors["surface"],
        foreground=colors["muted"],
        font=("TkDefaultFont", 8, "bold"),
    )
    style.configure(
        "RosterMetricValue.TLabel",
        background=colors["surface"],
        foreground=colors["text"],
        font=("TkDefaultFont", 16, "bold"),
    )
    style.configure(
        "Roster.TButton",
        background=colors["soft"],
        foreground=colors["text"],
        padding=(10, 7),
        relief="flat",
        borderwidth=1,
        bordercolor=colors["border"],
    )
    style.map(
        "Roster.TButton",
        background=[("active", colors["hover"]), ("pressed", colors["accent_soft"])],
        foreground=[("disabled", colors["muted"])],
    )
    style.configure(
        "RosterAccent.TButton",
        background=colors["accent"],
        foreground=colors["selection_text"],
        padding=(11, 8),
        font=("TkDefaultFont", 9, "bold"),
        relief="flat",
    )
    style.map(
        "RosterAccent.TButton",
        background=[("active", colors["accent_hover"]), ("pressed", colors["accent_hover"])],
        foreground=[("disabled", colors["muted"])],
    )
    style.configure(
        "RosterActive.TButton",
        background=colors["accent_soft"],
        foreground=colors["accent"],
        padding=(10, 7),
        font=("TkDefaultFont", 9, "bold"),
        relief="flat",
    )
    style.map(
        "RosterActive.TButton",
        background=[("active", colors["hover"]), ("pressed", colors["accent_soft"])],
    )
    style.configure(
        "Roster.TEntry",
        fieldbackground=colors["surface"],
        foreground=colors["text"],
        insertcolor=colors["text"],
        bordercolor=colors["border"],
        padding=8,
    )
    style.map("Roster.TEntry", bordercolor=[("focus", colors["accent"])])
    style.configure(
        "Roster.TCombobox",
        fieldbackground=colors["surface"],
        background=colors["surface"],
        foreground=colors["text"],
        arrowcolor=colors["accent"],
        bordercolor=colors["border"],
        padding=7,
    )
    style.map(
        "Roster.TCombobox",
        fieldbackground=[("readonly", colors["surface"])],
        selectbackground=[("readonly", colors["surface"])],
        selectforeground=[("readonly", colors["text"])],
        bordercolor=[("focus", colors["accent"])],
    )
    style.configure(
        "Roster.TCheckbutton",
        background=colors["soft"],
        foreground=colors["text"],
        indicatorcolor=colors["surface"],
        focuscolor=colors["accent"],
    )
    style.map(
        "Roster.TCheckbutton",
        background=[("active", colors["soft"])],
        indicatorcolor=[("selected", colors["accent"])],
    )
    style.configure(
        "Roster.Treeview",
        background=colors["surface"],
        fieldbackground=colors["surface"],
        foreground=colors["text"],
        rowheight=38,
        borderwidth=0,
    )
    style.configure(
        "Roster.Treeview.Heading",
        background=colors["soft"],
        foreground=colors["text"],
        padding=(8, 9),
        relief="flat",
        font=("TkDefaultFont", 9, "bold"),
    )
    style.map(
        "Roster.Treeview",
        background=[("selected", colors["accent_soft"])],
        foreground=[("selected", colors["text"])],
    )
    style.map("Roster.Treeview.Heading", background=[("active", colors["hover"])])
    style.configure(
        "Roster.Compact.Treeview",
        background=colors["soft"],
        fieldbackground=colors["soft"],
        foreground=colors["text"],
        rowheight=30,
        borderwidth=0,
    )
    style.configure(
        "Roster.Compact.Treeview.Heading",
        background=colors["surface"],
        foreground=colors["text"],
        padding=(7, 7),
        relief="flat",
        font=("TkDefaultFont", 9, "bold"),
    )
    style.map(
        "Roster.Compact.Treeview",
        background=[("selected", colors["accent_soft"])],
        foreground=[("selected", colors["text"])],
    )
    style.configure("Roster.TNotebook", background=colors["surface"], borderwidth=0)
    style.configure(
        "Roster.TNotebook.Tab",
        background=colors["soft"],
        foreground=colors["muted"],
        padding=(12, 8),
    )
    style.map(
        "Roster.TNotebook.Tab",
        background=[("selected", colors["accent_soft"]), ("active", colors["hover"])],
        foreground=[("selected", colors["accent"]), ("active", colors["text"])],
    )
    style.configure(
        "Roster.Horizontal.TProgressbar",
        troughcolor=colors["surface"],
        background=colors["accent"],
        bordercolor=colors["border"],
        lightcolor=colors["accent"],
        darkcolor=colors["accent"],
    )
    return colors


def _is_dark(value: str) -> bool:
    color = value.strip().lstrip("#")
    if len(color) != 6:
        return True
    try:
        red, green, blue = (int(color[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return True
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return luminance < 0.5

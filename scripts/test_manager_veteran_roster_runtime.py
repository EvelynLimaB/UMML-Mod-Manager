#!/usr/bin/env python3
"""Exercise the veteran roster lab with realistic extracted data."""

from __future__ import annotations

import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from umml_manager.store import ManagerStore
from umml_manager.ui_theme import configure_theme
from umml_manager.ui_veteran_lab import RosterLabPage
from umml_manager.veterans import VeteranStore

CASES = (
    ("minimum", 1020, 680, 1.0),
    ("minimum-scaled", 1020, 680, 1.35),
    ("desktop", 1366, 768, 1.0),
)


def _records() -> list[dict]:
    return [
        {
            "trained_chara_id": 7001,
            "chara_id": 1001,
            "card_id": 100101,
            "chara_name": "Special Week",
            "rank": "UG",
            "speed": 1200,
            "stamina": 800,
            "power": 1100,
            "guts": 500,
            "wiz": 900,
            "proper_distance_long": 8,
            "proper_running_style_senko": 7,
            "factor_info_array": [
                {"factor_id": 101, "factor_name": "Speed", "level": 3},
                {"factor_id": 202, "factor_name": "Long Distance", "level": 2},
            ],
            "skill_array": [
                {"skill_id": 10, "skill_name": "Corner Adept", "level": 1},
                {"skill_id": 11, "skill_name": "Straightaway Adept", "level": 1},
            ],
        },
        {
            "trained_chara_id": 7002,
            "chara_id": 1002,
            "card_id": 100201,
            "chara_name": "Silence Suzuka",
            "rank": "SS",
            "speed": 1300,
            "stamina": 600,
            "power": 980,
            "guts": 420,
            "wisdom": 1050,
            "proper_distance_mile": 8,
            "proper_running_style_nige": 8,
            "factor_info_array": [
                {"factor_id": 303, "factor_name": "Mile", "level": 2},
            ],
            "skill_array": [
                {"skill_id": 12, "skill_name": "Concentration", "level": 1},
            ],
        },
        {
            "trained_chara_id": 7003,
            "chara_id": 1001,
            "card_id": 100102,
            "chara_name": "Special Week",
            "rank": "S",
            "speed": 1100,
            "stamina": 1000,
            "power": 1000,
            "guts": 550,
            "wisdom": 800,
            "proper_distance_long": 7,
            "factor_info_array": [
                {"factor_id": 101, "factor_name": "Speed", "level": 1},
                {"factor_id": 404, "factor_name": "Stamina", "level": 1},
                {"factor_id": 505, "factor_name": "URA Scenario", "level": 1},
            ],
            "skill_array": [],
        },
    ]


def _build_app(root: tk.Tk, base: Path):
    manager = ManagerStore(base / "manager")
    source = base / "trained_chara_data.json"
    source.write_text(json.dumps(_records()), encoding="utf-8")
    VeteranStore(manager.paths.root / "veterans").import_json(source)
    return SimpleNamespace(
        root=root,
        store=manager,
        status=tk.StringVar(master=root, value="Ready"),
    )


def _assert_inside(parent: tk.Misc, widget: tk.Misc, label: str) -> None:
    parent.update_idletasks()
    left = parent.winfo_rootx() - 2
    right = left + parent.winfo_width() + 4
    top = parent.winfo_rooty() - 2
    bottom = top + parent.winfo_height() + 4
    widget_left = widget.winfo_rootx()
    widget_right = widget_left + widget.winfo_width()
    widget_top = widget.winfo_rooty()
    widget_bottom = widget_top + widget.winfo_height()
    if (
        widget_left < left
        or widget_right > right
        or widget_top < top
        or widget_bottom > bottom
    ):
        raise RuntimeError(
            f"{label} escaped its roster viewport: widget="
            f"{widget_left}:{widget_right},{widget_top}:{widget_bottom}; "
            f"viewport={left}:{right},{top}:{bottom}"
        )


def exercise_case(label: str, width: int, height: int, scaling: float) -> None:
    with tempfile.TemporaryDirectory(prefix=f"umm-veteran-{label}-") as temp:
        root = tk.Tk()
        root.withdraw()
        root.tk.call("tk", "scaling", scaling)
        configure_theme(root)
        app = _build_app(root, Path(temp))
        window = tk.Toplevel(root)
        window.geometry(f"{width}x{height}+0+0")
        window.minsize(1020, 680)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        page = RosterLabPage(window, app)
        page.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
        window.update_idletasks()
        window.update()

        try:
            if len(page.tree.get_children()) != 3:
                raise RuntimeError(f"Roster rendered {len(page.tree.get_children())} rows, expected 3")
            if page.detail_notebook.index("end") != 4:
                raise RuntimeError("Roster detail notebook did not expose four readable tabs")
            if page.metric_values["veterans"].get() != "3":
                raise RuntimeError("Roster summary did not count imported veterans")
            if page.factor_summary_value.get() != "2 factor(s) · 5 known stars · 1 at 3★":
                raise RuntimeError(
                    f"Unexpected selected factor summary: {page.factor_summary_value.get()}"
                )
            if len(page.factor_tree.get_children()) != 2:
                raise RuntimeError("Selected veteran factors were not rendered")
            if len(page.skill_tree.get_children()) != 2:
                raise RuntimeError("Selected veteran skills were not rendered")
            if len(page.aptitude_tree.get_children()) != 2:
                raise RuntimeError("Selected veteran aptitudes were not rendered")

            page.toggle_legacy_shortlist()
            window.update_idletasks()
            first = page.tree.item(page.tree.get_children()[0], "text")
            if first != "Special Week":
                raise RuntimeError(f"Legacy shortlist did not rank the 3★ record first: {first}")

            page.pin_selected()
            page.tree.selection_set("record-1")
            page._record_selected()
            if str(page.compare_button.cget("state")) != "normal":
                raise RuntimeError("Pin/compare workflow did not become available")

            page.clear_filters()
            page.tree.selection_set("record-0")
            page._record_selected()
            page.toggle_same_character()
            window.update_idletasks()
            if len(page.tree.get_children()) != 2:
                raise RuntimeError("Same-character tool did not isolate matching veterans")

            for widget, widget_label in (
                (page.search_entry, "Search"),
                (page.sort_box, "Sort"),
                (page.clear_search_button, "Clear filters"),
                (page.export_json_button, "Export snapshot"),
                (page.tree, "Roster table"),
                (page.detail_notebook, "Veteran details"),
            ):
                _assert_inside(page, widget, f"{widget_label} at {label}")
        finally:
            window.destroy()
            root.destroy()

    print(f"Veteran roster GUI case passed: {label} ({width}x{height}, scaling {scaling})")


def main() -> int:
    for case in CASES:
        exercise_case(*case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

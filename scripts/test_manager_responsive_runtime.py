#!/usr/bin/env python3
"""Exercise responsive Manager pages at supported desktop sizes."""

from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path

from umml_manager.gui import ManagerGUI
from umml_manager.safety import hash_file
from umml_manager.store import ManagerStore
from umml_manager.ui_scrollable import ScrollablePage, responsive_columns

CASES = (
    ("minimum", 980, 650, 1.0),
    ("minimum-scaled", 980, 650, 1.35),
    ("720p", 1280, 720, 1.0),
    ("1080p", 1920, 1080, 1.0),
)


def _build_store(base: Path) -> ManagerStore:
    game = base / "game"
    dat = game / "UmamusumePrettyDerby_Data" / "Persistent" / "dat"
    meta = base / "meta.db"
    dat.mkdir(parents=True)
    meta.write_bytes(b"disposable-responsive-gui-smoke-metadata")
    store = ManagerStore(base / "manager")
    store.save_settings(
        {
            "dat_path": str(dat),
            "meta_path": str(meta),
            "game_dir": str(game),
            "region": "global",
            "installation_key": "responsive-gui-smoke",
            "metadata_fingerprint": hash_file(meta),
        }
    )
    return store


def _assert_inside_viewport(page: ScrollablePage, widget, label: str) -> None:
    page.scroll_to_top()
    page.update_idletasks()
    widget.focus_force()
    widget.event_generate("<FocusIn>")
    page.update_idletasks()
    page.update()

    viewport_top = page.canvas.winfo_rooty()
    viewport_bottom = viewport_top + page.canvas.winfo_height()
    widget_top = widget.winfo_rooty()
    widget_bottom = widget_top + widget.winfo_height()
    if widget_top < viewport_top - 2 or widget_bottom > viewport_bottom + 2:
        raise RuntimeError(
            f"{label} was not revealed by keyboard focus: "
            f"widget={widget_top}:{widget_bottom}, "
            f"viewport={viewport_top}:{viewport_bottom}, yview={page.canvas.yview()}"
        )


def _assert_page_geometry(app: ManagerGUI, label: str) -> None:
    settings = app.settings
    studio = app.studio
    for page_name, page in (("Settings", settings), ("Studio", studio)):
        if not isinstance(page, ScrollablePage):
            raise RuntimeError(f"{page_name} is not using the document scroll container")
        if page.canvas.winfo_width() <= 1 or page.canvas.winfo_height() <= 1:
            raise RuntimeError(f"{page_name} did not receive a usable viewport at {label}")
        if abs(page.content.winfo_width() - page.canvas.winfo_width()) > 2:
            raise RuntimeError(
                f"{page_name} content width drifted from its viewport at {label}: "
                f"content={page.content.winfo_width()}, canvas={page.canvas.winfo_width()}"
            )

    compact_settings = settings.viewport_width < 860
    appearance_row = int(settings.appearance_controls.grid_info()["row"])
    expected_appearance_row = 1 if compact_settings else 0
    if appearance_row != expected_appearance_row:
        raise RuntimeError(
            f"Settings did not reflow at {label}: viewport={settings.viewport_width}, "
            f"controls row={appearance_row}, expected={expected_appearance_row}"
        )

    expected_columns = responsive_columns(studio.viewport_width, breakpoint=840)
    used_columns = {
        int(card.grid_info()["column"])
        for card, _description in studio._legacy_cards
    }
    if len(used_columns) != expected_columns:
        raise RuntimeError(
            f"Studio did not reflow at {label}: viewport={studio.viewport_width}, "
            f"columns={sorted(used_columns)}, expected={expected_columns}"
        )

    app.show_page("settings")
    app.root.update_idletasks()
    app.root.update()
    _assert_inside_viewport(settings, settings.open_data_button, f"Settings final action at {label}")

    app.show_page("studio")
    app.root.update_idletasks()
    app.root.update()
    final_tool = app.studio.tool_buttons["database"]
    _assert_inside_viewport(studio, final_tool, f"Studio final tool at {label}")


def exercise_case(label: str, width: int, height: int, scaling: float) -> None:
    with tempfile.TemporaryDirectory(prefix=f"umm-responsive-{label}-") as temp:
        root = tk.Tk()
        root.tk.call("tk", "scaling", scaling)
        app = ManagerGUI(root, _build_store(Path(temp)), auto_network=False)
        try:
            root.geometry(f"{width}x{height}+0+0")
            root.update_idletasks()
            root.update()
            for page_name in ("library", "discover", "studio", "conflicts", "settings"):
                app.show_page(page_name)
                root.update_idletasks()
                root.update()
            _assert_page_geometry(app, label)
        finally:
            app.close()
    print(f"Responsive GUI case passed: {label} ({width}x{height}, scaling {scaling})")


def main() -> int:
    for case in CASES:
        exercise_case(*case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

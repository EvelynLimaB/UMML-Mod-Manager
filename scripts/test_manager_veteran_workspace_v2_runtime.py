#!/usr/bin/env python3
"""Verify the corrected roster grid and incremental portrait presentation."""

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

from test_manager_veteran_master_runtime import _create_master, _seed_cached_portrait
from umml_manager.store import ManagerStore
from umml_manager.ui_theme import configure_theme
from umml_manager.ui_veteran_presenter_v2 import VeteranRosterPage
from umml_manager.veterans import VeteranStore


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="umm-veteran-workspace-v2-") as temp:
        base = Path(temp)
        persistent = base / "game" / "UmamusumePrettyDerby_Data" / "Persistent"
        dat = persistent / "dat"
        dat.mkdir(parents=True)
        meta = persistent / "meta"
        meta.write_bytes(b"runtime fixture metadata")
        _create_master(persistent / "master" / "master.mdb")

        manager_store = ManagerStore(base / "manager")
        source = base / "trained_chara_data.json"
        source.write_text(
            json.dumps(
                [
                    {
                        "trained_chara_id": 55,
                        "card_id": 100101,
                        "speed": 1200,
                        "stamina": 800,
                        "power": 1100,
                        "guts": 500,
                        "wiz": 900,
                        "factor_id_array": [101],
                        "skill_id_array": [10071],
                    }
                ]
            ),
            encoding="utf-8",
        )
        veteran_store = VeteranStore(manager_store.paths.root / "veterans")
        veteran_store.import_json(source)
        _seed_cached_portrait(veteran_store, 100101)

        root = tk.Tk()
        root.geometry("1500x900+0+0")
        configure_theme(root)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        app = SimpleNamespace(
            root=root,
            store=manager_store,
            dat_path=tk.StringVar(master=root, value=str(dat)),
            meta_path=tk.StringVar(master=root, value=str(meta)),
            game_dir=tk.StringVar(master=root, value=str(base / "game")),
            status=tk.StringVar(master=root, value="Ready"),
        )
        app._run_task = lambda *_args, **_kwargs: None

        page = VeteranRosterPage(root, app)
        page.configure_workspace_rows()
        page.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        try:
            root.update_idletasks()
            root.update()

            if page._main_workspace is None:
                raise RuntimeError("main roster workspace was not identified")
            if int(page._main_workspace.grid_info()["row"]) != 4:
                raise RuntimeError("main roster workspace does not own row 4")
            if page._credits_footer is None:
                raise RuntimeError("credit footer was not identified")
            if page._credits_footer.winfo_ismapped():
                raise RuntimeError("credit footer should be hidden with setup collapsed")

            # Tk on Windows returns an empty grid_info mapping for a widget
            # hidden with grid_remove. Briefly remap it to inspect the retained
            # row, then restore the intended collapsed state.
            page._credits_footer.grid()
            root.update_idletasks()
            footer_row = int(page._credits_footer.grid_info()["row"])
            page._credits_footer.grid_remove()
            root.update_idletasks()
            if footer_row != 5:
                raise RuntimeError("credit footer still overlaps the main workspace")

            if int(page.grid_rowconfigure(3)["weight"]) != 0:
                raise RuntimeError("collapsed summary row still consumes flexible space")
            if int(page.grid_rowconfigure(4)["weight"]) != 1:
                raise RuntimeError("main roster workspace is not the flexible row")

            chrome = page.quick_search_entry.master
            gap = page._main_workspace.winfo_y() - (chrome.winfo_y() + chrome.winfo_height())
            if gap > 24:
                raise RuntimeError(f"unexpected empty vertical gap above roster: {gap}px")
            if not page.chrome_status_value.get().startswith("1/1 veterans"):
                raise RuntimeError(
                    f"visible roster count is incorrect: {page.chrome_status_value.get()}"
                )
            items = page.tree.get_children()
            if not items or not str(page.tree.item(items[0], "image")):
                raise RuntimeError("roster row has neither portrait nor loading placeholder")
            if page._portrait_progress_host.winfo_ismapped():
                raise RuntimeError("portrait progress should collapse when everything is cached")
        finally:
            root.destroy()

    print("Veteran workspace v2 grid and portrait runtime passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

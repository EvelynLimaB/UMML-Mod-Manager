#!/usr/bin/env python3
"""Render the final veteran workspace with synthetic local master data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from umml_manager.store import ManagerStore
from umml_manager.ui_theme import configure_theme
from umml_manager.ui_veteran_presenter import VeteranRosterPage
from umml_manager.veteran_media import character_image_url
from umml_manager.veterans import VeteranStore, row_from_record


def _create_master(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE text_data(category INTEGER, "index" INTEGER, text TEXT);
            CREATE TABLE card_data(id INTEGER PRIMARY KEY, chara_id INTEGER);
            CREATE TABLE succession_factor(
                factor_id INTEGER PRIMARY KEY,
                factor_group_id INTEGER,
                rarity INTEGER,
                factor_type INTEGER,
                effect_group_id INTEGER
            );
            CREATE TABLE skill_data(
                id INTEGER PRIMARY KEY,
                rarity INTEGER,
                group_id INTEGER,
                icon_id INTEGER
            );
            """
        )
        connection.executemany(
            'INSERT INTO text_data(category, "index", text) VALUES (?, ?, ?)',
            (
                (4, 100101, "Special Dreamer Special Week"),
                (5, 100101, "Special Dreamer"),
                (6, 1001, "Special Week"),
                (47, 10071, "Corner Adept"),
                (48, 10071, "Slightly increase velocity on a corner."),
                (147, 101, "Speed Spark"),
                (172, 101, "Increases inherited Speed."),
            ),
        )
        connection.execute(
            "INSERT INTO card_data(id, chara_id) VALUES (100101, 1001)"
        )
        connection.execute(
            """
            INSERT INTO succession_factor(
                factor_id, factor_group_id, rarity, factor_type, effect_group_id
            ) VALUES (101, 10, 3, 1, 20)
            """
        )
        connection.execute(
            "INSERT INTO skill_data(id, rarity, group_id, icon_id) VALUES (10071, 1, 701, 10071)"
        )
        connection.commit()
    finally:
        connection.close()


def _seed_cached_portrait(veteran_store: VeteranStore, card_id: int) -> Path:
    url = character_image_url(card_id)
    if not url:
        raise RuntimeError("fixture card did not produce a portrait URL")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    cache_dir = veteran_store.root / "media-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"portrait-{digest}.png"
    Image.new("RGBA", (180, 220), (60, 170, 100, 255)).save(destination, format="PNG")
    return destination


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="umm-veteran-master-runtime-") as temp:
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
        cached_portrait = _seed_cached_portrait(veteran_store, 100101)

        root = tk.Tk()
        root.geometry("1320x820+0+0")
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

        def _unexpected_task(*_args, **_kwargs):
            raise RuntimeError("cached portrait unexpectedly started a network task")

        app._run_task = _unexpected_task
        page = VeteranRosterPage(root, app)
        page.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        try:
            root.update_idletasks()
            root.update()
            if len(page.records) != 1:
                raise RuntimeError("master-resolved workspace did not load one veteran")
            row = row_from_record(0, page.records[0])
            if row.name != "Special Dreamer Special Week" or row.chara_id != "1001":
                raise RuntimeError(f"card identity was not resolved: {row}")
            factor_items = page.factor_tree.get_children()
            skill_items = page.skill_tree.get_children()
            if not factor_items or page.factor_tree.item(factor_items[0], "text") != "Speed Spark":
                raise RuntimeError("factor name or level was not rendered from master data")
            if not skill_items or page.skill_tree.item(skill_items[0], "text") != "Corner Adept":
                raise RuntimeError("skill name was not rendered from master data")
            tabs = [page.detail_notebook.tab(tab_id, "text") for tab_id in page.detail_notebook.tabs()]
            if "Media" not in tabs:
                raise RuntimeError(f"optional Media tab is missing: {tabs}")
            page.detail_notebook.select(page.media_tab)
            root.update_idletasks()
            if not page.load_media_button.winfo_ismapped():
                raise RuntimeError("explicit artwork action is not visible")
            if not page.primary_portrait_label.winfo_ismapped():
                raise RuntimeError("primary selected-veteran portrait is not visible")
            if not str(page.primary_portrait_label.cget("image")):
                raise RuntimeError("cached costume artwork was not rendered in the main detail header")
            selected_item = page.tree.selection()
            if not selected_item or not str(page.tree.item(selected_item[0], "image")):
                raise RuntimeError("selected roster row did not receive its cached portrait thumbnail")
            if list((page.store.root / "media-cache").glob("*.png")) != [cached_portrait]:
                raise RuntimeError("the cached-only render unexpectedly changed portrait storage")
            if "resolved read-only" not in page.tool_hint_value.get():
                raise RuntimeError("read-only master-data provenance is not visible")
        finally:
            root.destroy()
    print("Master-resolved veteran workspace and primary portrait runtime passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

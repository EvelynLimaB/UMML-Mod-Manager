from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from umml_manager.veteran_local_portraits import LocalPortraitCache


class VeteranLocalPortraitTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path, Path]:
        persistent = root / "Persistent"
        master = persistent / "master" / "master.mdb"
        meta = persistent / "meta"
        dat = persistent / "dat"
        master.parent.mkdir(parents=True)
        dat.mkdir(parents=True)

        connection = sqlite3.connect(master)
        try:
            connection.executescript(
                """
                CREATE TABLE card_data(id INTEGER PRIMARY KEY, chara_id INTEGER);
                CREATE TABLE card_rarity_data(
                    card_id INTEGER,
                    rarity INTEGER,
                    race_dress_id INTEGER
                );
                INSERT INTO card_data(id, chara_id) VALUES (100101, 1001);
                INSERT INTO card_rarity_data(card_id, rarity, race_dress_id)
                    VALUES (100101, 3, 106);
                """
            )
            connection.commit()
        finally:
            connection.close()

        digest = "AB0123456789"
        logical = "3d/chara/stand/chara_stand_1001_000106.unity3d"
        connection = sqlite3.connect(meta)
        try:
            connection.execute("CREATE TABLE a(n TEXT, h TEXT)")
            connection.execute("INSERT INTO a(n, h) VALUES (?, ?)", (logical, digest))
            connection.commit()
        finally:
            connection.close()

        bundle = dat / "AB" / digest
        bundle.parent.mkdir(parents=True)
        bundle.write_bytes(b"synthetic unity bundle placeholder")
        return master, meta, dat, bundle

    def test_resolves_meta_hash_and_caches_manager_png(self) -> None:
        with tempfile.TemporaryDirectory(prefix="umm-local-portrait-") as temp:
            root = Path(temp)
            master, meta, dat, bundle = self._fixture(root)
            calls: list[tuple[Path, tuple[str, ...], Path]] = []

            def extractor(source: Path, stems: tuple[str, ...], target: Path) -> bool:
                calls.append((source, stems, target))
                Image.new("RGBA", (64, 64), (20, 120, 80, 255)).save(target, "PNG")
                return True

            cache = LocalPortraitCache(
                root / "cache",
                master_path=master,
                meta_path=meta,
                dat_root=dat,
                extractor=extractor,
            )
            first = cache.extract(100101)
            self.assertEqual(first.source_bundle, bundle.resolve())
            self.assertIsNotNone(first.portrait)
            self.assertTrue(first.portrait.is_file())
            self.assertFalse(first.cache_hit)
            self.assertIn("chara_stand_1001_000106", first.logical_name)
            self.assertEqual(len(calls), 1)
            self.assertIn("chara_stand_1001_000106", calls[0][1])

            second = cache.extract(100101)
            self.assertTrue(second.cache_hit)
            self.assertEqual(second.portrait, first.portrait)
            self.assertEqual(len(calls), 1)

    def test_like_wildcards_in_portrait_stem_are_escaped(self) -> None:
        with tempfile.TemporaryDirectory(prefix="umm-local-portrait-like-") as temp:
            root = Path(temp)
            master, meta, dat, _bundle = self._fixture(root)
            decoy_hash = "CD0123456789"
            connection = sqlite3.connect(meta)
            try:
                connection.execute(
                    "INSERT INTO a(n, h) VALUES (?, ?)",
                    (
                        "3d/chara/stand/charaXstandX1001X000106.unity3d",
                        decoy_hash,
                    ),
                )
                connection.commit()
            finally:
                connection.close()
            decoy = dat / "CD" / decoy_hash
            decoy.parent.mkdir(parents=True)
            decoy.write_bytes(b"decoy")

            cache = LocalPortraitCache(
                root / "cache",
                master_path=master,
                meta_path=meta,
                dat_root=dat,
                extractor=lambda *_args: False,
            )
            candidates = cache._bundle_candidates(("chara_stand_1001_000106",))
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0][1], "AB0123456789")

    def test_malformed_meta_hash_cannot_escape_dat_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="umm-local-portrait-traversal-") as temp:
            root = Path(temp)
            master, meta, dat, _bundle = self._fixture(root)
            outside = root / "outside.unity3d"
            outside.write_bytes(b"must not be read")
            connection = sqlite3.connect(meta)
            try:
                connection.execute(
                    "UPDATE a SET h = ?",
                    ("../../outside.unity3d",),
                )
                connection.commit()
            finally:
                connection.close()
            calls: list[Path] = []

            def extractor(source: Path, _stems: tuple[str, ...], _target: Path) -> bool:
                calls.append(source)
                return False

            cache = LocalPortraitCache(
                root / "cache",
                master_path=master,
                meta_path=meta,
                dat_root=dat,
                extractor=extractor,
            )
            result = cache.extract(100101)
            self.assertIsNone(result.portrait)
            self.assertEqual(calls, [])
            self.assertEqual(cache._bundle_path("../../outside.unity3d"), None)

    def test_missing_installation_fails_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="umm-local-portrait-missing-") as temp:
            root = Path(temp)
            cache = LocalPortraitCache(
                root / "cache",
                master_path=root / "missing-master",
                meta_path=root / "missing-meta",
                dat_root=root / "missing-dat",
            )
            result = cache.extract(100101)
            self.assertIsNone(result.portrait)
            self.assertIn("unavailable", result.warning)
            self.assertEqual(list((root / "cache").glob("*.png")), [])

    def test_extract_many_deduplicates_card_ids(self) -> None:
        with tempfile.TemporaryDirectory(prefix="umm-local-portrait-many-") as temp:
            root = Path(temp)
            master, meta, dat, _bundle = self._fixture(root)
            calls = 0

            def extractor(_source: Path, _stems: tuple[str, ...], target: Path) -> bool:
                nonlocal calls
                calls += 1
                Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(target, "PNG")
                return True

            cache = LocalPortraitCache(
                root / "cache",
                master_path=master,
                meta_path=meta,
                dat_root=dat,
                extractor=extractor,
            )
            results = cache.extract_many((100101, "100101", 0, None))
            self.assertEqual(len(results), 1)
            self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()

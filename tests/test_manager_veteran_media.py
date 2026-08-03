import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from umml_manager.veteran_media import (
    MAX_SKILL_ICONS,
    VeteranMediaCache,
    character_image_url,
    is_allowed_media_url,
    skill_image_url,
)


class _Response:
    def __init__(self, data: bytes, url: str, content_type: str = "image/png"):
        self.data = data
        self.url = url
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        }
        self._offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, size=-1):
        if size < 0:
            size = len(self.data) - self._offset
        chunk = self.data[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class _Opener:
    def __init__(self, data: bytes, content_type: str = "image/png"):
        self.data = data
        self.content_type = content_type
        self.calls = []

    def open(self, request, timeout=0):
        self.calls.append((request.full_url, timeout))
        return _Response(self.data, request.full_url, self.content_type)


def _png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGBA", (64, 64), (40, 180, 100, 255)).save(stream, format="PNG")
    return stream.getvalue()


class VeteranMediaTests(unittest.TestCase):
    def test_urls_are_derived_only_from_positive_game_ids(self):
        self.assertEqual(
            character_image_url(100101),
            "https://gametora.com/images/umamusume/characters/"
            "chara_stand_1001_100101.png",
        )
        self.assertEqual(
            skill_image_url(10071),
            "https://media.gametora.com/umamusume/skills/icon/10071.png",
        )
        self.assertIsNone(character_image_url(0))
        self.assertIsNone(skill_image_url("not-an-id"))

    def test_media_allowlist_rejects_downgrades_credentials_and_lookalikes(self):
        self.assertTrue(is_allowed_media_url(skill_image_url(10071)))
        self.assertFalse(is_allowed_media_url("http://media.gametora.com/x.png"))
        self.assertFalse(is_allowed_media_url("https://media.gametora.com.evil.test/x.png"))
        self.assertFalse(is_allowed_media_url("https://user@media.gametora.com/x.png"))
        self.assertFalse(is_allowed_media_url("https://media.gametora.com:444/x.png"))

    def test_cached_lookup_does_not_initialize_networking(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch(
                "umml_manager.veteran_media.create_ssl_context",
                side_effect=AssertionError("cache lookup initialized networking"),
            ) as create_context:
                cache = VeteranMediaCache(Path(temp))
                result = cache.cached_selection(100101, [10071])

            self.assertIsNone(result.portrait)
            self.assertEqual(result.skill_icons, ())
            create_context.assert_not_called()

    def test_downloads_validated_pngs_once_then_uses_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            opener = _Opener(_png_bytes())
            cache = VeteranMediaCache(Path(temp), opener=opener)

            first = cache.fetch_selection(100101, [10071, 10072])
            self.assertIsNotNone(first.portrait)
            self.assertEqual(len(first.skill_icons), 2)
            self.assertEqual(first.downloads, 3)
            self.assertEqual(first.cache_hits, 0)
            self.assertEqual(len(opener.calls), 3)
            for path in [first.portrait, *(item[1] for item in first.skill_icons)]:
                self.assertTrue(path.is_file())
                with Image.open(path) as image:
                    self.assertEqual(image.format, "PNG")

            second = cache.fetch_selection(100101, [10071, 10072])
            self.assertEqual(second.downloads, 0)
            self.assertEqual(second.cache_hits, 3)
            self.assertEqual(len(opener.calls), 3)

    def test_symlinked_cache_entry_is_replaced_not_trusted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            opener = _Opener(_png_bytes())
            cache = VeteranMediaCache(root, opener=opener)
            url = character_image_url(100101)
            target = cache._cache_path(url, "portrait")
            outside = root / "outside.png"
            outside.write_bytes(b"not manager cache")
            try:
                os.symlink(outside, target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this runner")

            cached = cache.cached_selection(100101, [])
            self.assertIsNone(cached.portrait)

            result = cache.fetch_selection(100101, [])
            self.assertEqual(result.downloads, 1)
            self.assertEqual(len(opener.calls), 1)
            self.assertFalse(target.is_symlink())
            self.assertEqual(outside.read_bytes(), b"not manager cache")

    def test_non_image_response_is_reported_without_poisoning_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            opener = _Opener(b"not an image", content_type="text/html")
            cache = VeteranMediaCache(Path(temp), opener=opener)

            result = cache.fetch_selection(100101, [])
            self.assertIsNone(result.portrait)
            self.assertTrue(result.warnings)
            self.assertEqual(list(Path(temp).glob("*.png")), [])

    def test_skill_icon_work_is_bounded_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            opener = _Opener(_png_bytes())
            cache = VeteranMediaCache(Path(temp), opener=opener)
            skill_ids = [10000 + index for index in range(MAX_SKILL_ICONS + 10)]
            skill_ids.extend(skill_ids[:5])

            result = cache.fetch_selection(None, skill_ids)
            self.assertEqual(len(result.skill_icons), MAX_SKILL_ICONS)
            self.assertEqual(len(opener.calls), MAX_SKILL_ICONS)

    def test_clear_removes_only_manager_png_cache_entries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            opener = _Opener(_png_bytes())
            cache = VeteranMediaCache(root, opener=opener)
            cache.fetch_selection(100101, [10071])
            unrelated = root / "keep.txt"
            unrelated.write_text("keep", encoding="utf-8")

            removed = cache.clear()
            self.assertEqual(removed, 2)
            self.assertTrue(unrelated.is_file())
            self.assertEqual(list(root.glob("*.png")), [])


if __name__ == "__main__":
    unittest.main()

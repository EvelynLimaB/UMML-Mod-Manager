from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from umml_manager.veteran_media import VeteranMediaResult
from umml_manager.veteran_portrait_loader import VeteranPortraitResolver


class _LocalStub:
    def __init__(self, root: Path, *, cached: bool = False, available: bool = True):
        self.path = root / "local.png"
        self.cached_enabled = cached
        self.available = available
        self.calls = 0
        if cached:
            self.path.write_bytes(b"png")

    def cached(self, _card_id):
        return self.path if self.cached_enabled else None

    def extract(self, card_id):
        self.calls += 1
        if not self.available:
            return SimpleNamespace(
                card_id=int(card_id),
                portrait=None,
                cache_hit=False,
                warning="local missing",
            )
        self.path.write_bytes(b"png")
        return SimpleNamespace(
            card_id=int(card_id),
            portrait=self.path,
            cache_hit=False,
            warning="",
        )


class _RemoteStub:
    def __init__(self, root: Path, *, available: bool = True):
        self.path = root / "remote.png"
        self.available = available
        self.fetch_calls: list[tuple[object, tuple[object, ...]]] = []

    def cached_selection(self, _card_id, _skill_ids):
        return VeteranMediaResult(None, (), 0, 0)

    def fetch_selection(self, card_id, skill_ids):
        normalized = tuple(skill_ids)
        self.fetch_calls.append((card_id, normalized))
        if not self.available:
            return VeteranMediaResult(None, (), 0, 0, ("remote missing",))
        self.path.write_bytes(b"png")
        return VeteranMediaResult(self.path if card_id else None, (), 0, 1)


class VeteranPortraitResolverTests(unittest.TestCase):
    def test_cached_portrait_skips_both_providers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = _LocalStub(root, cached=True)
            remote = _RemoteStub(root)
            result = VeteranPortraitResolver(local, remote).resolve(100101)
            self.assertEqual(result.source, "cache")
            self.assertTrue(result.cache_hit)
            self.assertEqual(local.calls, 0)
            self.assertEqual(remote.fetch_calls, [])

    def test_installed_game_is_used_before_remote_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = _LocalStub(root, available=True)
            remote = _RemoteStub(root)
            result = VeteranPortraitResolver(local, remote).resolve(100101)
            self.assertEqual(result.source, "local")
            self.assertEqual(local.calls, 1)
            self.assertEqual(remote.fetch_calls, [])

    def test_automatic_resolution_never_starts_remote_request(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = _LocalStub(root, available=False)
            remote = _RemoteStub(root)
            result = VeteranPortraitResolver(local, remote).resolve(100101)
            self.assertEqual(result.source, "local-unavailable")
            self.assertIsNone(result.portrait)
            self.assertEqual(remote.fetch_calls, [])

    def test_remote_is_used_only_after_explicit_permission(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = _LocalStub(root, available=False)
            remote = _RemoteStub(root)
            result = VeteranPortraitResolver(local, remote).resolve(
                100101,
                allow_remote=True,
            )
            self.assertEqual(result.source, "remote")
            self.assertEqual(remote.fetch_calls, [("100101", ())])

    def test_skill_icon_resolution_does_not_request_a_portrait(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            local = _LocalStub(root)
            remote = _RemoteStub(root)
            VeteranPortraitResolver(local, remote).resolve_skill_icons((10, 20))
            self.assertEqual(remote.fetch_calls, [(0, (10, 20))])


if __name__ == "__main__":
    unittest.main()

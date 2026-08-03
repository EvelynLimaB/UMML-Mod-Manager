from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from umml_manager.gamebanana_browser_bridge import (
    BrowserFileExpectation,
    _archive_name_matches,
    _requires_browser_download,
    wait_for_browser_download,
)
from umml_manager.providers.gamebanana_previews import PreviewGameBananaClient


class GameBananaBrowserBridgeTests(unittest.TestCase):
    def test_bridge_is_installed_on_interactive_client(self):
        self.assertTrue(
            getattr(PreviewGameBananaClient, "_umml_browser_bridge", False)
        )
        self.assertEqual(
            PreviewGameBananaClient.import_mod.__module__,
            "umml_manager.gamebanana_browser_bridge",
        )

    def test_only_html_download_failures_request_browser_fallback(self):
        browser_error = urllib.error.URLError(
            "GameBanana returned a web or error document instead of the "
            "selected mod file (Content-Type: text/html; URL: "
            "https://gamebanana.com/mmdl/1765152). No safe GameBanana CDN "
            "link was present in the response."
        )
        self.assertTrue(_requires_browser_download(browser_error))
        self.assertFalse(
            _requires_browser_download(
                urllib.error.URLError("certificate verify failed")
            )
        )

    def test_browser_filename_matching_accepts_duplicate_suffix(self):
        expected = BrowserFileExpectation(1765152, "sukumizu.zip")
        self.assertTrue(_archive_name_matches(Path("sukumizu.zip"), expected))
        self.assertTrue(_archive_name_matches(Path("sukumizu (1).zip"), expected))
        self.assertFalse(_archive_name_matches(Path("unrelated.zip"), expected))
        self.assertFalse(
            _archive_name_matches(Path("sukumizu.zip.crdownload"), expected)
        )

    def test_browser_download_is_detected_and_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            downloads = Path(temp) / "Downloads"
            downloads.mkdir()
            payload = b"PK\x03\x04browser-assisted-gamebanana-fixture"
            expected = BrowserFileExpectation(
                1765152,
                "sukumizu.zip",
                len(payload),
                hashlib.md5(payload, usedforsecurity=False).hexdigest(),
            )

            def browser_open(url: str) -> bool:
                self.assertEqual(url, "https://gamebanana.com/dl/1765152")
                (downloads / "sukumizu (1).zip").write_bytes(payload)
                return True

            with patch.dict(
                os.environ,
                {"UMML_GAMEBANANA_DOWNLOAD_DIR": str(downloads)},
                clear=False,
            ):
                result = wait_for_browser_download(
                    "https://gamebanana.com/dl/1765152",
                    expected,
                    timeout=2,
                    poll=0.01,
                    opener=browser_open,
                )
            self.assertEqual(
                os.path.normcase(str(result.resolve())),
                os.path.normcase(str((downloads / "sukumizu (1).zip").resolve())),
            )

    def test_browser_bridge_rejects_external_download_page(self):
        with self.assertRaisesRegex(Exception, "Unsafe GameBanana browser URL"):
            wait_for_browser_download(
                "https://example.com/sukumizu.zip",
                BrowserFileExpectation(1765152, "sukumizu.zip"),
                timeout=0.01,
                opener=lambda _url: True,
            )


if __name__ == "__main__":
    unittest.main()

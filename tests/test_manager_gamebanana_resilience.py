import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from umml_manager.providers.gamebanana_previews import (
    CACHE_MAX_AGE_SECONDS,
    CORE_DETAIL_FIELDS,
    PreviewGameBananaClient,
    normalize_file_records,
)
from umml_manager.store import StoreError


class _Response:
    def __init__(self, value, url: str):
        self.payload = json.dumps(value).encode("utf-8")
        self.url = url
        self.headers = {"Content-Length": str(len(self.payload))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, amount=-1):
        if amount is None or amount < 0:
            return self.payload
        return self.payload[:amount]

    def geturl(self):
        return self.url


class GameBananaResilienceTests(unittest.TestCase):
    def test_v11_503_falls_back_to_core_catalog_and_details(self):
        calls: list[str] = []

        def opener(request, timeout=0):
            del timeout
            url = request.full_url
            calls.append(url)
            if "/apiv11/" in url:
                raise urllib.error.HTTPError(
                    url,
                    503,
                    "Service Unavailable",
                    None,
                    None,
                )
            if "/Core/List/New" in url:
                return _Response([123], url)
            if "/Core/Item/Data" in url:
                values = {
                    "name": "Fallback mod",
                    "Owner().name": "Creator",
                    "Url().sProfileUrl()": "https://gamebanana.com/mods/123",
                    "text": "Works through Core",
                    "date": 100,
                    "mdate": 200,
                    "views": 300,
                    "likes": 4,
                    "downloads": 500,
                    "Preview().sSubFeedImageUrl()": "",
                    "RootCategory().name": "Skins",
                    "Game().name": "Umamusume: Pretty Derby (Global)",
                    "is_obsolete": False,
                    "Files().aFiles()": {
                        "https://gamebanana.com/dl/456": "fallback.zip"
                    },
                }
                return _Response(
                    [values[field] for field in CORE_DETAIL_FIELDS],
                    url,
                )
            self.fail(f"Unexpected URL: {url}")

        with tempfile.TemporaryDirectory() as temporary:
            client = PreviewGameBananaClient(
                opener=opener,
                cache_root=Path(temporary),
                sleeper=lambda _delay: None,
                clock=lambda: 1000.0,
            )

            page = client.browse(region="global", per_page=24)

        self.assertEqual(len(page.mods), 1)
        mod = page.mods[0]
        self.assertEqual(mod.id, 123)
        self.assertEqual(mod.name, "Fallback mod")
        self.assertEqual(mod.author, "Creator")
        self.assertEqual(mod.downloads, 500)
        self.assertEqual(len(mod.files), 1)
        self.assertEqual(mod.files[0].id, 456)
        self.assertEqual(mod.files[0].name, "fallback.zip")
        self.assertEqual(
            sum("/apiv11/" in url for url in calls),
            3,
            "The open v11 circuit should prevent another three detail retries",
        )
        self.assertTrue(any("/Core/List/New" in url for url in calls))
        self.assertTrue(any("/Core/Item/Data" in url for url in calls))

    def test_browse_uses_recent_cache_when_both_api_hosts_fail(self):
        def working(request, timeout=0):
            del timeout
            url = request.full_url
            if "/apiv11/Mod/Index" in url:
                return _Response(
                    {
                        "_aRecords": [
                            {
                                "_idRow": 77,
                                "_sName": "Cached mod",
                                "_aSubmitter": {"_sName": "Creator"},
                                "_aFiles": [],
                                "_sProfileUrl": "https://gamebanana.com/mods/77",
                                "_nDownloadCount": 42,
                            }
                        ],
                        "_aMetadata": {
                            "_nRecordCount": 1,
                            "_bIsComplete": True,
                        },
                    },
                    url,
                )
            self.fail(f"Unexpected URL: {url}")

        def unavailable(request, timeout=0):
            del timeout
            url = request.full_url
            raise urllib.error.HTTPError(
                url,
                503,
                "Service Unavailable",
                None,
                None,
            )

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            first = PreviewGameBananaClient(
                opener=working,
                cache_root=cache,
                sleeper=lambda _delay: None,
                clock=lambda: 1000.0,
            )
            fresh = first.browse(region="global")
            self.assertEqual(fresh.mods[0].downloads, 42)

            second = PreviewGameBananaClient(
                opener=unavailable,
                cache_root=cache,
                sleeper=lambda _delay: None,
                clock=lambda: 1001.0,
            )
            cached = second.browse(region="global")

        self.assertEqual(cached.mods[0].name, "Cached mod")
        self.assertIn("cached results", second.last_notice)

    def test_expired_cache_is_not_used(self):
        def working(request, timeout=0):
            del timeout
            url = request.full_url
            return _Response(
                {
                    "_aRecords": [
                        {
                            "_idRow": 88,
                            "_sName": "Soon stale",
                            "_aSubmitter": {"_sName": "Creator"},
                            "_aFiles": [],
                        }
                    ],
                    "_aMetadata": {
                        "_nRecordCount": 1,
                        "_bIsComplete": True,
                    },
                },
                url,
            )

        def unavailable(request, timeout=0):
            del timeout
            url = request.full_url
            raise urllib.error.HTTPError(
                url,
                503,
                "Service Unavailable",
                None,
                None,
            )

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            PreviewGameBananaClient(
                opener=working,
                cache_root=cache,
                sleeper=lambda _delay: None,
                clock=lambda: 1000.0,
            ).browse(region="global")
            client = PreviewGameBananaClient(
                opener=unavailable,
                cache_root=cache,
                sleeper=lambda _delay: None,
                clock=lambda: 1000.0 + CACHE_MAX_AGE_SECONDS + 1,
            )

            with self.assertRaisesRegex(
                StoreError,
                "temporarily unavailable",
            ):
                client.browse(region="global")

    def test_core_file_mapping_is_normalized(self):
        result = normalize_file_records(
            {
                "https://gamebanana.com/dl/987": "mod-file.zip",
            }
        )

        self.assertEqual(
            result,
            [
                {
                    "_idRow": 987,
                    "_sFile": "mod-file.zip",
                    "_sDownloadUrl": "https://gamebanana.com/dl/987",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()

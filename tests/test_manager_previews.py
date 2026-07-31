import io
import unittest
import urllib.request
from unittest.mock import patch

from umml_manager.providers import default_provider_registry
from umml_manager.providers.gamebanana_previews import (
    PreviewGameBananaClient,
    normalize_file_records,
    primary_preview_url,
)

try:
    from PIL import Image
except ImportError:  # Legacy-only validation intentionally installs no manager deps.
    Image = None

if Image is not None:
    from umml_manager.preview_images import (
        MAX_PREVIEW_BYTES,
        GameBananaPreviewRedirectHandler,
        PreviewImageError,
        PreviewImageLoader,
        decode_preview_image,
    )


class PreviewUrlTests(unittest.TestCase):
    def test_base_url_without_trailing_slash_is_joined_correctly(self):
        data = {
            "_aPreviewMedia": {
                "_aImages": [
                    {
                        "_sBaseUrl": "https://images.gamebanana.com/img/ss/mods",
                        "_sFile": "original.jpg",
                        "_sFile220": "220-90_original.jpg",
                        "_sFile530": "530-90_original.jpg",
                    }
                ]
            }
        }
        self.assertEqual(
            primary_preview_url(data),
            "https://images.gamebanana.com/img/ss/mods/530-90_original.jpg",
        )

    def test_preview_client_normalizes_provider_media(self):
        data = {
            "_idRow": 123,
            "_sName": "Synthetic mod",
            "_aPreviewMedia": {
                "_aImages": [
                    {
                        "_sBaseUrl": "https://images.gamebanana.com/img/ss/mods",
                        "_sFile530": "530-90_image.jpg",
                    }
                ]
            },
        }
        client = PreviewGameBananaClient(opener=lambda *_args, **_kwargs: None)
        self.assertEqual(
            client._mod(data).image_url,
            "https://images.gamebanana.com/img/ss/mods/530-90_image.jpg",
        )

    def test_file_mapping_is_normalized_for_install_selection(self):
        data = {
            "_idRow": 123,
            "_sName": "Synthetic mod",
            "_aFiles": {
                "991": {
                    "_idRow": 991,
                    "_sFile": "synthetic.zip",
                    "_sDownloadUrl": "https://gamebanana.com/dl/991",
                    "_nDownloadCount": 12,
                },
                "metadata": {"note": "not a downloadable file"},
            },
        }
        client = PreviewGameBananaClient(opener=lambda *_args, **_kwargs: None)
        mod = client._mod(data)
        self.assertEqual(len(mod.files), 1)
        self.assertEqual(mod.files[0].id, 991)
        self.assertEqual(mod.files[0].name, "synthetic.zip")
        self.assertEqual(mod.files[0].downloads, 12)

    def test_nested_file_container_is_normalized(self):
        records = normalize_file_records(
            {
                "_aFiles": [
                    {
                        "_idFile": 55,
                        "_sFile": "nested.zip",
                        "_sDownloadUrlArchive": "https://gamebanana.com/dl/55",
                    }
                ]
            }
        )
        self.assertEqual([item["_idFile"] for item in records], [55])

    def test_default_registry_uses_preview_aware_provider(self):
        provider = default_provider_registry().get("gamebanana")
        self.assertIsInstance(provider, PreviewGameBananaClient)

    def test_non_https_preview_is_ignored(self):
        data = {
            "_aPreviewMedia": {
                "_aImages": [
                    {
                        "_sBaseUrl": "http://images.gamebanana.com/img/ss/mods",
                        "_sFile530": "530-90_original.jpg",
                    }
                ]
            }
        }
        self.assertEqual(primary_preview_url(data), "")

    def test_external_https_preview_is_ignored(self):
        data = {
            "_aPreviewMedia": {
                "_aImages": [
                    {
                        "_sBaseUrl": "https://example.invalid/tracker",
                        "_sFile530": "image.jpg",
                    }
                ]
            }
        }
        self.assertEqual(primary_preview_url(data), "")

    def test_gui_client_does_not_fall_back_to_untrusted_legacy_url(self):
        data = {
            "_idRow": 123,
            "_sName": "Synthetic mod",
            "_aPreviewMedia": {
                "_aImages": [
                    {
                        "_sBaseUrl": "https://example.invalid/tracker",
                        "_sFile": "image.jpg",
                    }
                ]
            },
        }
        client = PreviewGameBananaClient(opener=lambda *_args, **_kwargs: None)
        self.assertEqual(client._mod(data).image_url, "")


class FakeHeaders(dict):
    def get_content_type(self):
        value = str(self.get("Content-Type", ""))
        return value.split(";", 1)[0].strip()


class FakeResponse:
    def __init__(
        self,
        payload: bytes,
        *,
        url: str = "https://images.gamebanana.com/test.png",
        content_type: str = "image/png",
        content_length: int | None = None,
    ):
        self.payload = payload
        self.url = url
        self.headers = FakeHeaders(
            {
                "Content-Type": content_type,
                "Content-Length": str(
                    len(payload) if content_length is None else content_length
                ),
            }
        )

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        return False

    def geturl(self):
        return self.url

    def read(self, size=-1):
        return self.payload if size < 0 else self.payload[:size]


def png_bytes(size=(800, 400)) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, "white").save(stream, format="PNG")
    return stream.getvalue()


@unittest.skipUnless(Image is not None, "Pillow is a manager-only dependency")
class ManagerPreviewTests(unittest.TestCase):
    def test_verified_preview_is_loaded_and_scaled(self):
        payload = png_bytes()
        response = FakeResponse(payload)
        loader = PreviewImageLoader(opener=lambda _request, timeout=30: response)

        preview = loader.load(
            "https://images.gamebanana.com/test.png",
            max_size=(200, 100),
        )

        self.assertEqual(preview.image.size, (200, 100))
        self.assertEqual(preview.content_type, "image/png")
        self.assertEqual(preview.byte_size, len(payload))
        self.assertEqual(
            preview.source_url,
            "https://images.gamebanana.com/test.png",
        )

    def test_http_preview_url_is_rejected_before_network_access(self):
        called = False

        def opener(_request, timeout=30):
            nonlocal called
            called = True
            return FakeResponse(b"")

        with self.assertRaises(PreviewImageError):
            PreviewImageLoader(opener=opener).load(
                "http://images.gamebanana.com/test.png"
            )
        self.assertFalse(called)

    def test_external_https_url_is_rejected_before_network_access(self):
        called = False

        def opener(_request, timeout=30):
            nonlocal called
            called = True
            return FakeResponse(b"")

        with self.assertRaises(PreviewImageError):
            PreviewImageLoader(opener=opener).load(
                "https://example.invalid/test.png"
            )
        self.assertFalse(called)

    def test_redirect_handler_rejects_external_host_before_following(self):
        request = urllib.request.Request(
            "https://images.gamebanana.com/test.png"
        )
        handler = GameBananaPreviewRedirectHandler()
        with self.assertRaises(PreviewImageError):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://example.invalid/tracker.png",
            )

    def test_downgraded_redirect_is_rejected(self):
        payload = png_bytes()
        response = FakeResponse(
            payload,
            url="http://images.gamebanana.com/test.png",
        )
        loader = PreviewImageLoader(opener=lambda _request, timeout=30: response)

        with self.assertRaises(PreviewImageError) as raised:
            loader.load("https://images.gamebanana.com/test.png")
        self.assertIn("GameBanana HTTPS", str(raised.exception))

    def test_non_image_content_type_is_rejected(self):
        response = FakeResponse(
            b"<html>not an image</html>",
            content_type="text/html; charset=utf-8",
        )
        loader = PreviewImageLoader(opener=lambda _request, timeout=30: response)

        with self.assertRaises(PreviewImageError) as raised:
            loader.load("https://images.gamebanana.com/test.png")
        self.assertIn("not an image", str(raised.exception))

    def test_oversized_declared_preview_is_rejected_without_reading(self):
        response = FakeResponse(
            b"small",
            content_length=MAX_PREVIEW_BYTES + 1,
        )
        loader = PreviewImageLoader(opener=lambda _request, timeout=30: response)

        with self.assertRaises(PreviewImageError) as raised:
            loader.load("https://images.gamebanana.com/test.png")
        self.assertIn("12 MiB", str(raised.exception))

    def test_malformed_image_bytes_are_rejected(self):
        with self.assertRaises(PreviewImageError) as raised:
            decode_preview_image(b"not really a picture")
        self.assertIn("could not be decoded", str(raised.exception))

    def test_pixel_limit_is_enforced_before_full_conversion(self):
        payload = png_bytes((20, 20))
        with patch("umml_manager.preview_images.MAX_PREVIEW_PIXELS", 100):
            with self.assertRaises(PreviewImageError) as raised:
                decode_preview_image(payload)
        self.assertIn("megapixel safety limit", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

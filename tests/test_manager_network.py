import http.cookiejar
import os
import ssl
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from umml_manager.network import (
    ProviderDownloadPolicy,
    TLSConfiguration,
    TLSConfigurationError,
    build_https_opener,
    create_ssl_context,
    resolve_tls_configuration,
    tls_diagnostics,
)
from umml_manager.providers.gamebanana import GameBananaClient
from umml_manager.store import StoreError


class ManagerNetworkTests(unittest.TestCase):
    def test_fedora_bazzite_system_bundle_is_used_when_build_paths_are_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "ca-bundle.crt"
            bundle.write_text("synthetic CA bundle", encoding="utf-8")
            defaults = SimpleNamespace(cafile=None, capath=None)
            with (
                patch.dict(os.environ, {}, clear=True),
                patch(
                    "umml_manager.network.ssl.get_default_verify_paths",
                    return_value=defaults,
                ),
                patch("umml_manager.network.SYSTEM_CA_FILES", (str(bundle),)),
            ):
                configuration = resolve_tls_configuration()
            self.assertEqual(configuration.source, "system trust store")
            self.assertEqual(configuration.cafile, str(bundle.resolve()))
            self.assertIsNone(configuration.capath)

    def test_explicit_missing_environment_bundle_fails_closed(self):
        with patch.dict(
            os.environ,
            {"SSL_CERT_FILE": "/definitely/missing/umml-ca.pem"},
            clear=True,
        ):
            with self.assertRaises(TLSConfigurationError) as context:
                resolve_tls_configuration()
        self.assertIn("SSL_CERT_FILE", str(context.exception))
        self.assertIn("missing or unreadable", str(context.exception))

    def test_ssl_context_loads_the_resolved_bundle(self):
        configuration = TLSConfiguration(
            cafile="/synthetic/ca.pem",
            capath=None,
            source="test",
        )
        context = MagicMock(spec=ssl.SSLContext)
        with (
            patch(
                "umml_manager.network.resolve_tls_configuration",
                return_value=configuration,
            ),
            patch(
                "umml_manager.network.ssl.create_default_context",
                return_value=context,
            ) as create_context,
        ):
            actual_context, actual_configuration = create_ssl_context()
        create_context.assert_called_once_with(
            cafile="/synthetic/ca.pem",
            capath=None,
        )
        self.assertIs(actual_context, context)
        self.assertEqual(actual_configuration, configuration)

    def test_https_opener_keeps_ephemeral_provider_cookies(self):
        configuration = TLSConfiguration(
            cafile="/synthetic/ca.pem",
            capath=None,
            source="test",
        )
        context = MagicMock(spec=ssl.SSLContext)
        built = MagicMock(spec=urllib.request.OpenerDirector)
        with (
            patch(
                "umml_manager.network.create_ssl_context",
                return_value=(context, configuration),
            ),
            patch(
                "umml_manager.network.urllib.request.build_opener",
                return_value=built,
            ) as build_opener,
        ):
            opener, actual_configuration = build_https_opener()

        self.assertIs(opener, built)
        self.assertEqual(actual_configuration, configuration)
        handlers = build_opener.call_args.args
        self.assertTrue(
            any(isinstance(handler, ProviderDownloadPolicy) for handler in handlers)
        )
        cookie_handlers = [
            handler
            for handler in handlers
            if isinstance(handler, urllib.request.HTTPCookieProcessor)
        ]
        self.assertEqual(len(cookie_handlers), 1)
        self.assertIsInstance(cookie_handlers[0].cookiejar, http.cookiejar.CookieJar)
        self.assertEqual(list(cookie_handlers[0].cookiejar), [])

    def test_gamebanana_download_policy_adds_site_context(self):
        policy = ProviderDownloadPolicy()
        for path in ("/dl/456", "/download/456", "/mmdl/456"):
            with self.subTest(path=path):
                request = urllib.request.Request(f"https://gamebanana.com{path}")
                processed = policy.https_request(request)
                self.assertEqual(
                    processed.get_header("Referer"),
                    "https://gamebanana.com/",
                )
                self.assertIn(
                    "application/octet-stream",
                    processed.get_header("Accept"),
                )

    def test_gamebanana_download_policy_does_not_touch_other_hosts(self):
        request = urllib.request.Request("https://example.com/download/456")
        processed = ProviderDownloadPolicy().https_request(request)

        self.assertIsNone(processed.get_header("Referer"))
        self.assertIsNone(processed.get_header("Accept"))

    def test_gamebanana_download_policy_rejects_html_payload(self):
        request = urllib.request.Request("https://gamebanana.com/dl/456")
        policy = ProviderDownloadPolicy()
        policy.https_request(request)
        response = MagicMock()
        response.headers = {"Content-Type": "text/html; charset=utf-8"}

        with self.assertRaisesRegex(
            urllib.error.URLError,
            "web or error document",
        ):
            policy.https_response(request, response)
        response.close.assert_called_once_with()

    def test_gamebanana_download_policy_accepts_archive_payload(self):
        request = urllib.request.Request("https://gamebanana.com/dl/456")
        policy = ProviderDownloadPolicy()
        policy.https_request(request)
        response = MagicMock()
        response.headers = {"Content-Type": "application/octet-stream"}

        self.assertIs(policy.https_response(request, response), response)
        response.close.assert_not_called()

    def test_gamebanana_certificate_failure_is_actionable_and_stays_verified(self):
        verification_error = ssl.SSLCertVerificationError(
            1,
            "certificate verify failed: unable to get local issuer certificate",
        )

        def opener(_request, timeout=30):
            raise urllib.error.URLError(verification_error)

        with self.assertRaises(StoreError) as context:
            GameBananaClient(opener=opener).fetch("123")
        message = str(context.exception)
        self.assertIn("TLS certificate verification failed", message)
        self.assertIn("Do not disable certificate verification", message)
        self.assertIn("custom opener", message)

    def test_tls_diagnostics_report_selected_source_without_network_request(self):
        configuration = TLSConfiguration(
            cafile="/synthetic/ca.pem",
            capath=None,
            source="bundled certifi",
        )
        with (
            patch(
                "umml_manager.network.resolve_tls_configuration",
                return_value=configuration,
            ),
            patch("umml_manager.network.ssl.create_default_context"),
        ):
            report, ready = tls_diagnostics()
        self.assertTrue(ready)
        self.assertIn("HTTPS certificate verification: READY", report)
        self.assertIn("bundled certifi", report)
        self.assertIn("/synthetic/ca.pem", report)


if __name__ == "__main__":
    unittest.main()

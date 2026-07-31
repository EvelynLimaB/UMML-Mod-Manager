import os
import ssl
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from umml_manager.network import (
    TLSConfiguration,
    TLSConfigurationError,
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

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from umml_manager.legacy_adapter import LegacyAssetAdapter
from umml_manager.store import StoreError


class LegacyDecoderCompatibilityTests(unittest.TestCase):
    @staticmethod
    def _adapter() -> LegacyAssetAdapter:
        adapter = LegacyAssetAdapter.__new__(LegacyAssetAdapter)
        adapter.meta_path = Path("/tmp/metadata.db")
        return adapter

    @staticmethod
    def _host(result: tuple[int, int]):
        class Host:
            def decrypt_assets_internal(
                self,
                src_root,
                dst_root,
                use_hash=False,
                filter_path=None,
            ):
                self.last_decode = (
                    src_root,
                    dst_root,
                    use_hash,
                    filter_path,
                )
                return result

        return Host

    def _decoder_for(self, **exports):
        core = types.ModuleType("UMML_core")
        for name, value in exports.items():
            setattr(core, name, value)
        with patch.dict(sys.modules, {"UMML_core": core}):
            return self._adapter()._decoder()

    def test_current_modloadergui_backend_is_supported(self):
        decoder = self._decoder_for(ModLoaderGUI=self._host((4, 1)))
        self.assertEqual(
            decoder.decrypt_assets_internal("source", "target"),
            (4, 1),
        )
        self.assertEqual(
            decoder.last_decode,
            ("source", "target", False, None),
        )

    def test_historical_ummlapp_backend_remains_supported(self):
        decoder = self._decoder_for(UMMLApp=self._host((2, 0)))
        self.assertEqual(
            decoder.decrypt_assets_internal(
                "source",
                "target",
                use_hash=True,
                filter_path="body",
            ),
            (2, 0),
        )
        self.assertEqual(
            decoder.last_decode,
            ("source", "target", True, "body"),
        )

    def test_ummlapp_takes_precedence_when_both_names_exist(self):
        historical = self._host((8, 0))
        current = self._host((9, 0))
        decoder = self._decoder_for(
            UMMLApp=historical,
            ModLoaderGUI=current,
        )
        self.assertEqual(
            decoder.decrypt_assets_internal("source", "target"),
            (8, 0),
        )

    def test_missing_decoder_api_fails_with_actionable_error(self):
        with self.assertRaisesRegex(
            StoreError,
            "UMMLApp or ModLoaderGUI",
        ):
            self._decoder_for()


if __name__ == "__main__":
    unittest.main()

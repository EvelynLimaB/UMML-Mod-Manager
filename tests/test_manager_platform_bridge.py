import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import umml_platform
from umml_autodetect import (
    DataCandidate,
    DiscoveryResult,
    GameCandidate,
    GLOBAL_APP_ID,
)
from umml_manager import platform_bridge


class ManagerPlatformBridgeTests(unittest.TestCase):
    def _ready_result(self, root: Path) -> DiscoveryResult:
        game = root / "game"
        data = root / "persistent"
        (data / "dat").mkdir(parents=True)
        (data / "meta").write_bytes(b"encrypted metadata")
        game.mkdir()
        return DiscoveryResult(
            GLOBAL_APP_ID,
            game,
            data,
            game_candidates=[
                GameCandidate(game, "process:123:STEAM_COMPAT_INSTALL_PATH", 1250)
            ],
            data_candidates=[
                DataCandidate(data, "process:123:STEAM_COMPAT_DATA_PATH", 1425)
            ],
        )

    def test_manager_replaces_legacy_linux_miss_with_robust_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self._ready_result(Path(temp))
            legacy = [
                umml_platform.GameInstallation(
                    key="steam-global",
                    label="Steam Global",
                    region="Global",
                    game_dir=None,
                    data_dir=None,
                    meta_path=None,
                )
            ]
            with patch.object(platform_bridge, "IS_WINDOWS", False), patch.object(
                platform_bridge.umml_platform,
                "detect_installations",
                return_value=legacy,
            ), patch.object(
                platform_bridge,
                "discover_global_installation",
                return_value=result,
            ):
                detected = platform_bridge.detect_installations()

            self.assertEqual(len(detected), 1)
            self.assertTrue(detected[0].detected)
            self.assertEqual(detected[0].game_dir, result.game_dir)
            self.assertEqual(detected[0].data_dir, result.data_dir)
            self.assertIn(
                "process:123:STEAM_COMPAT_INSTALL_PATH",
                detected[0].note,
            )

    def test_manager_discovery_refreshes_on_every_attempt(self):
        legacy = [
            umml_platform.GameInstallation(
                key="steam-global",
                label="Steam Global",
                region="Global",
                game_dir=None,
                data_dir=None,
                meta_path=None,
            )
        ]
        missing = DiscoveryResult(GLOBAL_APP_ID, None, None)
        with tempfile.TemporaryDirectory() as temp:
            ready = self._ready_result(Path(temp))
            with patch.object(platform_bridge, "IS_WINDOWS", False), patch.object(
                platform_bridge.umml_platform,
                "detect_installations",
                return_value=legacy,
            ), patch.object(
                platform_bridge,
                "discover_global_installation",
                side_effect=(missing, ready),
            ) as discover:
                first = platform_bridge.detect_installations()
                second = platform_bridge.detect_installations()

            self.assertFalse(first[0].detected)
            self.assertTrue(second[0].detected)
            self.assertEqual(discover.call_count, 2)

    def test_manager_doctor_includes_robust_discovery_report(self):
        missing = DiscoveryResult(
            GLOBAL_APP_ID,
            None,
            None,
            notes=["No complete Steam/Proton pair."],
        )
        with patch.object(platform_bridge, "IS_WINDOWS", False), patch.object(
            platform_bridge.umml_platform,
            "detect_installations",
            return_value=[],
        ), patch.object(
            platform_bridge,
            "discover_global_installation",
            return_value=missing,
        ):
            report, ready = platform_bridge.format_doctor_report()

        self.assertFalse(ready)
        self.assertIn("UMML Manager platform doctor", report)
        self.assertIn("Steam autodetect report for app 3224770", report)
        self.assertIn("No complete Steam/Proton pair.", report)
        self.assertIn("MANAGER RESULT: NOT READY", report)

    def test_legacy_detector_prints_cannot_corrupt_cli_json(self):
        def noisy_legacy_detector():
            print("legacy parser warning")
            return []

        missing = DiscoveryResult(GLOBAL_APP_ID, None, None)
        output = io.StringIO()
        with patch.object(platform_bridge, "IS_WINDOWS", False), patch.object(
            platform_bridge.umml_platform,
            "detect_installations",
            side_effect=noisy_legacy_detector,
        ), patch.object(
            platform_bridge,
            "discover_global_installation",
            return_value=missing,
        ), redirect_stdout(output):
            platform_bridge.format_doctor_report()

        self.assertEqual(output.getvalue(), "")

    def test_windows_keeps_the_original_platform_detector(self):
        legacy = [
            umml_platform.GameInstallation(
                key="steam-global",
                label="Steam Global",
                region="Global",
                game_dir=None,
                data_dir=None,
                meta_path=None,
            )
        ]
        with patch.object(platform_bridge, "IS_WINDOWS", True), patch.object(
            platform_bridge.umml_platform,
            "detect_installations",
            return_value=legacy,
        ), patch.object(
            platform_bridge.umml_platform,
            "format_doctor_report",
            return_value=("Windows platform doctor", False),
        ), patch.object(
            platform_bridge,
            "discover_global_installation",
        ) as discover:
            detected = platform_bridge.detect_installations()
            report = platform_bridge.format_doctor_report()

        self.assertEqual(detected, legacy)
        self.assertEqual(report, ("Windows platform doctor", False))
        discover.assert_not_called()


if __name__ == "__main__":
    unittest.main()

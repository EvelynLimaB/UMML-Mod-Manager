import tempfile
import unittest
from pathlib import Path

from umml_manager.ui_theme import (
    DARK_PALETTE,
    LIGHT_PALETTE,
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    detect_system_theme,
    normalize_theme_mode,
    palette_for_mode,
    resolve_theme_mode,
)


class ManagerThemeTests(unittest.TestCase):
    def test_theme_mode_normalization_is_fail_safe(self):
        self.assertEqual(normalize_theme_mode("Dark"), THEME_DARK)
        self.assertEqual(normalize_theme_mode(" light "), THEME_LIGHT)
        self.assertEqual(normalize_theme_mode("unknown"), THEME_SYSTEM)
        self.assertEqual(normalize_theme_mode(None), THEME_SYSTEM)

    def test_explicit_theme_does_not_depend_on_desktop(self):
        env = {"GTK_THEME": "Adwaita-dark"}
        self.assertEqual(resolve_theme_mode(THEME_LIGHT, env=env), THEME_LIGHT)
        self.assertEqual(resolve_theme_mode(THEME_DARK, env={}), THEME_DARK)

    def test_environment_theme_names_are_detected(self):
        self.assertEqual(
            detect_system_theme(env={"GTK_THEME": "Adwaita-dark"}),
            THEME_DARK,
        )
        self.assertEqual(
            detect_system_theme(env={"KDE_COLOR_SCHEME": "BreezeLight"}),
            THEME_LIGHT,
        )
        self.assertEqual(
            detect_system_theme(env={"UMML_SYSTEM_THEME": "dark"}),
            THEME_DARK,
        )

    def test_kde_background_luminance_is_used_when_scheme_name_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / ".config" / "kdeglobals"
            config.parent.mkdir(parents=True)
            config.write_text(
                "[General]\nColorScheme=Breeze\n"
                "[Colors:Window]\nBackgroundNormal=24,31,27\n",
                encoding="utf-8",
            )
            self.assertEqual(
                detect_system_theme(env={}, home=root, platform_name="linux"),
                THEME_DARK,
            )

    def test_gtk_prefer_dark_setting_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / ".config" / "gtk-3.0" / "settings.ini"
            config.parent.mkdir(parents=True)
            config.write_text(
                "[Settings]\ngtk-application-prefer-dark-theme=1\n",
                encoding="utf-8",
            )
            self.assertEqual(
                detect_system_theme(env={}, home=root, platform_name="linux"),
                THEME_DARK,
            )

    def test_system_theme_has_a_predictable_light_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(
                detect_system_theme(
                    env={},
                    home=Path(temp),
                    platform_name="linux",
                ),
                THEME_LIGHT,
            )

    def test_palettes_keep_normal_text_at_accessible_contrast(self):
        for palette in (LIGHT_PALETTE, DARK_PALETTE):
            with self.subTest(palette=palette.name):
                self.assertGreaterEqual(
                    self._contrast_ratio(palette.text, palette.background),
                    4.5,
                )
                self.assertGreaterEqual(
                    self._contrast_ratio(palette.text, palette.surface),
                    4.5,
                )
                self.assertGreaterEqual(
                    self._contrast_ratio(palette.muted, palette.background),
                    4.5,
                )
                self.assertEqual(palette_for_mode(palette.name), palette)

    @classmethod
    def _contrast_ratio(cls, first: str, second: str) -> float:
        bright = max(cls._luminance(first), cls._luminance(second))
        dark = min(cls._luminance(first), cls._luminance(second))
        return (bright + 0.05) / (dark + 0.05)

    @staticmethod
    def _luminance(value: str) -> float:
        channels = [
            int(value[index : index + 2], 16) / 255
            for index in (1, 3, 5)
        ]
        linear = [
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


if __name__ == "__main__":
    unittest.main()

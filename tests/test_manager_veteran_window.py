import unittest

from umml_manager.ui_veterans_window import veteran_window_geometry


class _Window:
    def __init__(self, width: int, height: int, x: int = 0, y: int = 0):
        self.width = width
        self.height = height
        self.x = x
        self.y = y

    def winfo_vrootwidth(self):
        return self.width

    def winfo_vrootheight(self):
        return self.height

    def winfo_screenwidth(self):
        return self.width

    def winfo_screenheight(self):
        return self.height

    def winfo_vrootx(self):
        return self.x

    def winfo_vrooty(self):
        return self.y


def _parse_geometry(value: str) -> tuple[int, int, int, int]:
    dimensions, x, y = value.split("+")
    width, height = dimensions.split("x")
    return int(width), int(height), int(x), int(y)


class VeteranWindowGeometryTests(unittest.TestCase):
    def test_large_desktop_uses_almost_all_available_space(self):
        width, height, x, y = _parse_geometry(
            veteran_window_geometry(_Window(1920, 1080))
        )
        self.assertGreaterEqual(width, 1840)
        self.assertGreaterEqual(height, 980)
        self.assertLessEqual(x, 40)
        self.assertLessEqual(y, 50)

    def test_virtual_desktop_origin_is_preserved(self):
        width, height, x, y = _parse_geometry(
            veteran_window_geometry(_Window(1600, 900, x=1920, y=0))
        )
        self.assertGreaterEqual(width, 1530)
        self.assertGreaterEqual(height, 810)
        self.assertGreaterEqual(x, 1920)
        self.assertGreaterEqual(y, 0)

    def test_minimum_supported_size_remains_available(self):
        width, height, _x, _y = _parse_geometry(
            veteran_window_geometry(_Window(900, 620))
        )
        self.assertGreaterEqual(width, 1020)
        self.assertGreaterEqual(height, 680)


if __name__ == "__main__":
    unittest.main()

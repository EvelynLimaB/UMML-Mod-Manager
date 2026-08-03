from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from umml_manager.veteran_export import atomic_export_json
from umml_manager.veterans import VeteranDataError


class VeteranExportTests(unittest.TestCase):
    def test_atomic_export_writes_complete_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "selected.json"
            result = atomic_export_json(
                target,
                {"record": {"name": "Special Week", "factor": "3★"}},
            )

            self.assertEqual(result, target)
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")),
                {"record": {"name": "Special Week", "factor": "3★"}},
            )
            self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_export_refuses_symlink_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real_target = root / "private.json"
            real_target.write_text("keep", encoding="utf-8")
            link = root / "selected.json"
            try:
                os.symlink(real_target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this runner")

            with self.assertRaises(VeteranDataError):
                atomic_export_json(link, {"record": {"id": 1}})
            self.assertEqual(real_target.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()

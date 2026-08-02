import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from umml_manager.ui_veteran_external import (
    _open_extractor_log,
    _regular_file,
    _save_external_selection,
    build_external_launch,
)


class _Store:
    def __init__(self):
        self.settings = {}

    def load_settings(self):
        return dict(self.settings)

    def save_settings(self, value):
        self.settings = dict(value)


class ExternalVeteranExtractorTests(unittest.TestCase):
    def _write_werseter_source(self, root: Path) -> tuple[Path, Path]:
        project = root / "umadump"
        project.mkdir()
        script = project / "main.py"
        script.write_text("", encoding="utf-8")
        for name in ("memory.py", "json_encoders.py", "game_structs.py"):
            (project / name).write_text("", encoding="utf-8")
        (project / "requirements.txt").write_text(
            "minidump~=0.0.24\n",
            encoding="utf-8",
        )
        return project, script

    def test_standalone_extractor_runs_in_isolated_inbox(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "UmaExtractor.exe"
            executable.write_bytes(b"MZ")
            inbox = root / "inbox"

            launch = build_external_launch(executable, inbox)

            self.assertEqual(launch.command, (str(executable.resolve()),))
            self.assertEqual(launch.cwd, inbox.resolve())
            self.assertTrue(inbox.is_dir())

    def test_generic_python_extractor_uses_configured_interpreter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "extract_umas.py"
            script.write_text("print('ok')", encoding="utf-8")
            interpreter = root / "python-test"
            interpreter.write_text("fixture", encoding="utf-8")
            inbox = root / "inbox"

            launch = build_external_launch(
                script,
                inbox,
                python_executable=str(interpreter),
            )

            self.assertEqual(
                launch.command,
                (str(interpreter.resolve()), str(script.resolve())),
            )
            self.assertEqual(launch.cwd, inbox.resolve())

    def test_werseter_source_keeps_project_importable_with_explicit_python(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project, script = self._write_werseter_source(root)
            interpreter = root / "python-test"
            interpreter.write_text("fixture", encoding="utf-8")
            inbox = root / "inbox"

            with mock.patch(
                "umml_manager.ui_veteran_external._python_command_is_314",
                return_value=True,
            ):
                launch = build_external_launch(
                    script,
                    inbox,
                    python_executable=str(interpreter),
                )

            self.assertEqual(
                launch.command[0:2],
                (str(interpreter.resolve()), "-c"),
            )
            self.assertIn("--rerun-mode", launch.command[2])
            self.assertEqual(launch.command[-3], str(project.resolve()))
            self.assertEqual(launch.command[-2], str(script.resolve()))
            self.assertEqual(launch.command[-1], str(inbox.resolve()))
            self.assertEqual(launch.cwd, inbox.resolve())
            self.assertEqual(launch.provider_hint, "Werseter/umadump source")

    def test_frozen_manager_uses_bundled_extractor_host(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project, script = self._write_werseter_source(root)
            executable = root / "umml-manager-bin"
            executable.write_text("fixture", encoding="utf-8")
            inbox = root / "inbox"

            with (
                mock.patch.object(sys, "frozen", True, create=True),
                mock.patch.object(sys, "executable", str(executable)),
            ):
                launch = build_external_launch(script, inbox)

            self.assertEqual(launch.command[0], str(executable))
            self.assertEqual(launch.command[1], "--extractor-host")
            self.assertEqual(launch.command[2], str(project.resolve()))
            self.assertEqual(launch.command[3], str(script.resolve()))
            self.assertEqual(launch.command[4], str(inbox.resolve()))
            self.assertEqual(
                launch.provider_hint,
                "Werseter/umadump bundled runtime",
            )

    def test_missing_configured_interpreter_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "extract_umas.py"
            script.write_text("print('ok')", encoding="utf-8")

            with self.assertRaisesRegex(
                RuntimeError,
                "Configured extractor Python is missing",
            ):
                build_external_launch(
                    script,
                    root / "inbox",
                    python_executable=str(root / "missing-python"),
                )

    def test_extractor_log_is_regular_and_private(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "inbox" / "veteran-extractor.log"
            with _open_extractor_log(path) as stream:
                stream.write(b"test\n")

            self.assertTrue(_regular_file(path))
            self.assertEqual(path.read_bytes(), b"test\n")
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o077, 0)

    def test_extractor_log_refuses_symlink_without_touching_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside.log"
            outside.write_bytes(b"keep")
            link = root / "veteran-extractor.log"
            try:
                os.symlink(outside, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this runner")

            with self.assertRaises(OSError):
                _open_extractor_log(link)
            self.assertEqual(outside.read_bytes(), b"keep")
            self.assertFalse(_regular_file(link))

    def test_external_selection_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = root / "extractor.py"
            actual.write_text("print('ok')", encoding="utf-8")
            link = root / "linked.py"
            try:
                os.symlink(actual, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is unavailable on this runner")
            page = type("Page", (), {"store": _Store()})()

            with self.assertRaises(FileNotFoundError):
                _save_external_selection(page, link)
            self.assertEqual(page.store.settings, {})


if __name__ == "__main__":
    unittest.main()

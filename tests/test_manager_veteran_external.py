import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from umml_manager.ui_veteran_external import build_external_launch


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


if __name__ == "__main__":
    unittest.main()

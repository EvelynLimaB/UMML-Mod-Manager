import tempfile
import unittest
from pathlib import Path

from umml_manager.ui_veteran_external import build_external_launch


class ExternalVeteranExtractorTests(unittest.TestCase):
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

    def test_generic_python_extractor_uses_current_interpreter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "extract_umas.py"
            script.write_text("print('ok')", encoding="utf-8")
            inbox = root / "inbox"

            launch = build_external_launch(
                script,
                inbox,
                python_executable="python-test",
            )

            self.assertEqual(
                launch.command,
                ("python-test", str(script.resolve())),
            )
            self.assertEqual(launch.cwd, inbox.resolve())

    def test_werseter_source_keeps_project_importable_and_outputs_to_inbox(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "umadump"
            project.mkdir()
            script = project / "main.py"
            script.write_text("", encoding="utf-8")
            for name in ("memory.py", "json_encoders.py", "game_structs.py"):
                (project / name).write_text("", encoding="utf-8")
            inbox = root / "inbox"

            launch = build_external_launch(
                script,
                inbox,
                python_executable="python-test",
            )

            self.assertEqual(launch.command[0:2], ("python-test", "-c"))
            self.assertIn("--rerun-mode", launch.command[2])
            self.assertEqual(launch.command[-3], str(project.resolve()))
            self.assertEqual(launch.command[-2], str(script.resolve()))
            self.assertEqual(launch.command[-1], str(inbox.resolve()))
            self.assertEqual(launch.cwd, inbox.resolve())
            self.assertEqual(launch.provider_hint, "Werseter/umadump source")


if __name__ == "__main__":
    unittest.main()

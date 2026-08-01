import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from umml_manager.extractor_host import (
    ExtractorHostError,
    packaged_host_command,
    run_extractor,
    runtime_probe,
)


class PackagedExtractorHostTests(unittest.TestCase):
    def _write_project(
        self,
        root: Path,
        *,
        requirements: str = "minidump~=0.0.24\n",
    ) -> tuple[Path, Path]:
        project = root / "umadump-2.5.4"
        project.mkdir()
        script = project / "main.py"
        script.write_text(
            "import json,os,sys\n"
            "from pathlib import Path\n"
            "Path('host-result.json').write_text(json.dumps({"
            "'argv': sys.argv[1:], 'cwd': os.getcwd()}), encoding='utf-8')\n",
            encoding="utf-8",
        )
        for name in ("memory.py", "game_structs.py", "json_encoders.py"):
            (project / name).write_text("", encoding="utf-8")
        (project / "requirements.txt").write_text(
            requirements,
            encoding="utf-8",
        )
        return project, script

    def test_runtime_probe_requires_python_314_and_bundled_minidump(self):
        probe = runtime_probe()

        self.assertTrue(probe["python_314_or_newer"], probe)
        self.assertEqual(probe["minidump"], "0.0.24")
        self.assertTrue(probe["ready"], probe)

    def test_runs_recognized_source_in_isolated_inbox(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, script = self._write_project(root)
            inbox = root / "inbox"

            self.assertEqual(run_extractor(project, script, inbox), 0)

            result = json.loads(
                (inbox / "host-result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                result["argv"],
                ["--rerun-mode", "once", "--no-update-check"],
            )
            self.assertEqual(Path(result["cwd"]), inbox.resolve())

    def test_rejects_entry_point_outside_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, _script = self._write_project(root)
            outside = root / "main.py"
            outside.write_text("", encoding="utf-8")

            with self.assertRaisesRegex(
                ExtractorHostError,
                "inside its project directory",
            ):
                run_extractor(project, outside, root / "inbox")

    def test_rejects_unbundled_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, script = self._write_project(
                root,
                requirements="minidump~=0.0.24\nrequests==2.0\n",
            )

            with self.assertRaisesRegex(
                ExtractorHostError,
                "dependencies not bundled",
            ):
                run_extractor(project, script, root / "inbox")

    def test_frozen_command_reenters_manager_through_private_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, script = self._write_project(root)
            inbox = root / "inbox"
            executable = root / "umml-manager-bin"
            executable.write_text("fixture", encoding="utf-8")

            with (
                mock.patch.object(sys, "frozen", True, create=True),
                mock.patch.object(sys, "executable", str(executable)),
            ):
                command = packaged_host_command(project, script, inbox)

            self.assertEqual(command[0], str(executable))
            self.assertEqual(command[1], "--extractor-host")
            self.assertEqual(command[2], str(project.resolve()))
            self.assertEqual(command[3], str(script.resolve()))
            self.assertEqual(command[4], str(inbox.resolve()))


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from umml_manager.studio import (
    OpenPathError,
    external_process_environment,
    open_path,
)


class ExternalProcessEnvironmentTests(unittest.TestCase):
    def test_pyinstaller_library_path_is_restored_for_host_programs(self):
        env = external_process_environment(
            {
                "PATH": "/usr/bin",
                "LD_LIBRARY_PATH": "/tmp/_MEI12345",
                "LD_LIBRARY_PATH_ORIG": "/usr/local/lib:/usr/lib",
            }
        )
        self.assertEqual(env["LD_LIBRARY_PATH"], "/usr/local/lib:/usr/lib")
        self.assertNotIn("LD_LIBRARY_PATH_ORIG", env)

    def test_bundled_library_path_is_removed_without_an_original(self):
        env = external_process_environment(
            {
                "PATH": "/usr/bin",
                "LD_LIBRARY_PATH": "/tmp/_MEI12345",
            }
        )
        self.assertNotIn("LD_LIBRARY_PATH", env)


class LinuxOpenPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "manager data"
        self.folder.mkdir()

    @patch("umml_manager.studio.subprocess.run")
    @patch("umml_manager.studio.shutil.which")
    def test_kde_uses_native_opener_and_sanitized_environment(
        self,
        which: Mock,
        run: Mock,
    ):
        which.side_effect = lambda name, path=None: (
            f"/usr/bin/{name}" if name == "kioclient6" else None
        )
        run.return_value = subprocess.CompletedProcess([], 0, "", "")
        environment = {
            "PATH": "/usr/bin",
            "XDG_CURRENT_DESKTOP": "KDE",
            "LD_LIBRARY_PATH": "/tmp/_MEI12345",
            "LD_LIBRARY_PATH_ORIG": "/usr/lib64",
        }
        with patch.object(os, "environ", environment), patch(
            "umml_manager.studio.sys.platform",
            "linux",
        ):
            open_path(self.folder)

        command = run.call_args.args[0]
        used_env = run.call_args.kwargs["env"]
        self.assertEqual(command[0], "/usr/bin/kioclient6")
        self.assertEqual(command[1], "exec")
        self.assertEqual(command[2], self.folder.resolve().as_uri())
        self.assertEqual(used_env["LD_LIBRARY_PATH"], "/usr/lib64")
        self.assertNotIn("LD_LIBRARY_PATH_ORIG", used_env)

    @patch("umml_manager.studio.subprocess.run")
    @patch("umml_manager.studio.shutil.which")
    def test_failed_generic_opener_falls_back_to_xdg_open(
        self,
        which: Mock,
        run: Mock,
    ):
        available = {
            "gio": "/usr/bin/gio",
            "xdg-open": "/usr/bin/xdg-open",
        }
        which.side_effect = lambda name, path=None: available.get(name)
        run.side_effect = (
            subprocess.CompletedProcess([], 2, "", "gio failed"),
            subprocess.CompletedProcess([], 0, "", ""),
        )
        environment = {"PATH": "/usr/bin", "XDG_CURRENT_DESKTOP": "GNOME"}
        with patch.object(os, "environ", environment), patch(
            "umml_manager.studio.sys.platform",
            "linux",
        ):
            open_path(self.folder)

        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][0], "/usr/bin/gio")
        self.assertEqual(run.call_args_list[1].args[0][0], "/usr/bin/xdg-open")
        self.assertEqual(
            run.call_args_list[1].args[0][1],
            str(self.folder.resolve()),
        )

    @patch("umml_manager.studio.subprocess.Popen")
    @patch("umml_manager.studio.subprocess.run")
    @patch("umml_manager.studio.shutil.which")
    def test_direct_dolphin_fallback_is_considered_started_when_it_stays_open(
        self,
        which: Mock,
        run: Mock,
        popen: Mock,
    ):
        which.side_effect = lambda name, path=None: (
            "/usr/bin/xdg-open"
            if name == "xdg-open"
            else "/usr/bin/dolphin"
            if name == "dolphin"
            else None
        )
        run.return_value = subprocess.CompletedProcess([], 3, "", "helper missing")
        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("dolphin", 1.0)
        popen.return_value = process
        environment = {"PATH": "/usr/bin", "XDG_CURRENT_DESKTOP": "KDE"}
        with patch.object(os, "environ", environment), patch(
            "umml_manager.studio.sys.platform",
            "linux",
        ):
            open_path(self.folder)

        command = popen.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/dolphin")
        self.assertEqual(command[-1], str(self.folder.resolve()))

    @patch("umml_manager.studio.subprocess.Popen")
    @patch("umml_manager.studio.subprocess.run")
    @patch("umml_manager.studio.shutil.which")
    def test_all_opener_failures_are_reported_instead_of_disappearing(
        self,
        which: Mock,
        run: Mock,
        popen: Mock,
    ):
        which.side_effect = lambda name, path=None: (
            f"/usr/bin/{name}" if name in {"gio", "dolphin"} else None
        )
        run.return_value = subprocess.CompletedProcess([], 1, "", "no portal")
        process = Mock()
        process.wait.return_value = 1
        popen.return_value = process
        environment = {"PATH": "/usr/bin", "XDG_CURRENT_DESKTOP": "GNOME"}
        with patch.object(os, "environ", environment), patch(
            "umml_manager.studio.sys.platform",
            "linux",
        ):
            with self.assertRaisesRegex(OpenPathError, "Could not open") as raised:
                open_path(self.folder)

        self.assertIn("gio exited with status 1", str(raised.exception))
        self.assertIn("dolphin exited with status 1", str(raised.exception))

    def test_missing_path_is_rejected_before_launching_any_helper(self):
        missing = self.folder / "missing"
        with self.assertRaisesRegex(OpenPathError, "does not exist"):
            open_path(missing)


if __name__ == "__main__":
    unittest.main()

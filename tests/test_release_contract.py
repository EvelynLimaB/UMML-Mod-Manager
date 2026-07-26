import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_version_is_release_safe(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")

    def test_single_autodetection_engine_is_packaged(self):
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_release.sh").read_text(encoding="utf-8")
        source_entry = (ROOT / "UMML.py").read_text(encoding="utf-8")

        for text in (installer, builder, source_entry):
            self.assertIn("umml_autodetect", text)

        # Removed compatibility modules may be named only in installer cleanup,
        # never as required/package inputs.
        self.assertNotIn("sitecustomize.py", builder)
        self.assertNotIn("umml_detection_hotfix.py", builder)
        self.assertNotIn("umml_manual_location_fix.py", builder)
        for stale_variable in (
            "SOURCE_SITE=",
            "TARGET_SITE=",
            "SOURCE_HOTFIX=",
            "TARGET_HOTFIX=",
            "SOURCE_MANUAL=",
            "TARGET_MANUAL=",
        ):
            self.assertNotIn(stale_variable, installer)

        self.assertFalse((ROOT / "umml_detection_hotfix.py").exists())
        self.assertFalse((ROOT / "umml_manual_location_fix.py").exists())
        self.assertFalse((ROOT / "sitecustomize.py").exists())

    def test_installer_contains_complete_runtime(self):
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        for name in ("UMML.py", "UMML_core.py", "umml_platform.py", "UMML_data"):
            self.assertIn(name, installer)

    def test_manager_source_installer_contains_complete_runtime(self):
        installer = (ROOT / "install-manager.sh").read_text(encoding="utf-8")
        for copy_command in (
            'install -m 0644 "$SOURCE_ROOT/UMML.py" "$APP_DIR/UMML.py"',
            'install -m 0644 "$SOURCE_ROOT/UMML_core.py" "$APP_DIR/UMML_core.py"',
            'install -m 0644 "$SOURCE_ROOT/umml_platform.py" "$APP_DIR/umml_platform.py"',
            'cp -a "$SOURCE_ROOT/umml_autodetect" "$APP_DIR/umml_autodetect"',
            'cp -a "$SOURCE_ROOT/UMML_data" "$APP_DIR/UMML_data"',
        ):
            self.assertIn(copy_command, installer)
        self.assertIn("from PIL import Image, ImageTk", installer)
        self.assertIn("import certifi", installer)

    def test_source_release_includes_packaging_and_reference_files(self):
        builder = (ROOT / "scripts" / "build_release.sh").read_text(encoding="utf-8")
        for name in (
            "UMML.py", "UMML_core.py", "umml_packaged.py", "umml_platform.py",
            "umml_autodetect", "AUTODETECTION.md", "install.sh", "VERSION",
            "requirements-build.txt", "build_deb.sh", "build_appimage.sh", "umml.spec",
        ):
            self.assertIn(name, builder)

    def test_binary_package_definitions_exist(self):
        expected = (
            "requirements-build.txt",
            "packaging/pyinstaller/umml.spec",
            "packaging/linux/io.github.evelynlimab.umml.desktop",
            "packaging/linux/io.github.evelynlimab.umml.metainfo.xml",
            "scripts/build_frozen.sh",
            "scripts/build_deb.sh",
            "scripts/build_appimage.sh",
        )
        for relative in expected:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_entry_points_apply_autodetection(self):
        source = (ROOT / "UMML.py").read_text(encoding="utf-8")
        packaged = (ROOT / "umml_packaged.py").read_text(encoding="utf-8")
        self.assertIn("apply_autodetect()", source)
        self.assertIn("_MEIPASS", packaged)
        self.assertIn('"--version"', packaged)

    def test_release_workflow_exercises_real_layouts(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        for name in (
            "build_frozen.sh", "build_deb.sh", "build_appimage.sh",
            "compatdata/3224770", "libraryfolders.vdf", "Steam Global: Detected",
            "result: READY",
        ):
            self.assertIn(name, workflow)
        self.assertIn("*.deb", workflow)
        self.assertIn("*.AppImage", workflow)

    def test_readme_and_appstream_mention_current_version(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        metainfo = (
            ROOT / "packaging" / "linux" / "io.github.evelynlimab.umml.metainfo.xml"
        ).read_text(encoding="utf-8")
        self.assertIn(version, readme)
        self.assertIn(version, metainfo)

    def test_manager_docs_and_appstream_mention_current_version(self):
        version = (ROOT / "MANAGER_VERSION").read_text(
            encoding="utf-8"
        ).strip()
        appstream_version = version.replace("~alpha", "-alpha.")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        manager_readme = (ROOT / "MANAGER_README.md").read_text(
            encoding="utf-8"
        )
        metainfo = (
            ROOT
            / "packaging"
            / "linux"
            / "io.github.evelynlimab.ummlmanager.metainfo.xml"
        ).read_text(encoding="utf-8")
        changelog = (ROOT / "MANAGER_CHANGELOG.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(version, readme)
        self.assertIn(version, manager_readme)
        self.assertIn(appstream_version, metainfo)
        self.assertIn(version, changelog)

    def test_manager_checks_protect_main_and_exercise_finished_packages(self):
        workflow = (
            ROOT / ".github" / "workflows" / "manager-checks.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("      - main\n", workflow)
        for evidence in (
            "scripts/test_manager_source_install.sh",
            "scripts/test_manager_autodetect_runtime.py",
            "scripts/manager_main_gate.sh",
            "cli self-test",
            "gui --smoke-test",
            "--cli self-test",
            "--smoke-test",
            'sudo apt-get install -y "./$DEB"',
            "sudo apt-get remove -y umml-manager",
            "package-sentinel",
        ):
            self.assertIn(evidence, workflow)

        source_smoke = ROOT / "scripts" / "test_manager_source_install.sh"
        self.assertTrue(source_smoke.is_file())
        self.assertTrue(source_smoke.stat().st_mode & 0o111)

        promotion_gate = ROOT / "scripts" / "manager_main_gate.sh"
        self.assertTrue(promotion_gate.is_file())
        self.assertTrue(promotion_gate.stat().st_mode & 0o111)
        gate_text = promotion_gate.read_text(encoding="utf-8")
        for command in (
            "self-test",
            "doctor",
            "network-smoke",
            "--checksums",
            "--smoke-test",
            "verify-profile",
            "RESULT: PASS",
        ):
            self.assertIn(command, gate_text)

        autodetect_runtime = (
            ROOT / "scripts" / "test_manager_autodetect_runtime.py"
        )
        self.assertTrue(autodetect_runtime.is_file())
        self.assertTrue(autodetect_runtime.stat().st_mode & 0o111)

        promotion_policy = (
            ROOT / "docs" / "MANAGER_MAIN_PROMOTION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("stable Manager release", promotion_policy)
        self.assertIn("self-installing executable patch", promotion_policy)


if __name__ == "__main__":
    unittest.main()

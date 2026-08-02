import unittest

from scripts.audit_release import (
    ReleaseAuditError,
    manager_version,
    portable_version,
    release_tag,
    run_audit,
)


class ManagerReleaseAuditTests(unittest.TestCase):
    def test_current_repository_release_contract_passes(self):
        version = manager_version()
        display = portable_version(version)
        tag = release_tag(version)

        report = run_audit(tag)

        self.assertEqual(report["manager_version"], version)
        self.assertEqual(report["portable_version"], display)
        self.assertEqual(report["tag"], tag)
        self.assertEqual(
            report["release_notes"],
            f"docs/releases/{display}.md",
        )

    def test_version_forms_are_unambiguous(self):
        version = manager_version()
        display = version.replace("~alpha", "-alpha.")
        self.assertEqual(portable_version(version), display)
        self.assertEqual(release_tag(version), f"v{display}")

    def test_wrong_requested_tag_is_rejected(self):
        with self.assertRaises(ReleaseAuditError):
            run_audit("v0.0.0-alpha.0")

    def test_non_debian_prerelease_form_is_rejected(self):
        with self.assertRaises(ReleaseAuditError):
            portable_version("0.2.0-alpha.20")


if __name__ == "__main__":
    unittest.main()

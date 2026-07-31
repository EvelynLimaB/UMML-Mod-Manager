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
        report = run_audit("v0.2.0-alpha.19")
        self.assertEqual(report["manager_version"], "0.2.0~alpha19")
        self.assertEqual(report["portable_version"], "0.2.0-alpha.19")
        self.assertEqual(report["tag"], "v0.2.0-alpha.19")
        self.assertEqual(
            report["release_notes"],
            "docs/releases/0.2.0-alpha.19.md",
        )

    def test_version_forms_are_unambiguous(self):
        version = manager_version()
        self.assertEqual(portable_version(version), "0.2.0-alpha.19")
        self.assertEqual(release_tag(version), "v0.2.0-alpha.19")

    def test_wrong_requested_tag_is_rejected(self):
        with self.assertRaises(ReleaseAuditError):
            run_audit("v0.2.0-alpha.18")

    def test_non_debian_prerelease_form_is_rejected(self):
        with self.assertRaises(ReleaseAuditError):
            portable_version("0.2.0-alpha.19")


if __name__ == "__main__":
    unittest.main()

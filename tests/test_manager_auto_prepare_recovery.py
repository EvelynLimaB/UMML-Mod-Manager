from __future__ import annotations

import unittest
from types import SimpleNamespace

from umml_manager.models import PACKAGE_UMML_ASSETS
from umml_manager.ui_auto_prepare_actions import AutoPrepareActions


class _Probe(AutoPrepareActions):
    def __init__(self, needs: dict[str, bool]):
        self.needs = needs
        self._auto_prepare_failures = set()
        self._auto_prepare_error_messages = {}

    def _record_needs_auto_prepare(self, record) -> bool:
        return self.needs.get(record.id, False)


class _AfterRoot:
    def __init__(self):
        self.cancelled: list[str] = []
        self.bound = None
        self.callback = None

    def after(self, _delay, callback):
        self.callback = callback
        return "after-1"

    def after_cancel(self, callback_id):
        self.cancelled.append(callback_id)

    def bind(self, event_name, callback, add=None):
        self.bound = (event_name, callback, add)


class AutoPrepareRecoveryTests(unittest.TestCase):
    @staticmethod
    def _record(mod_id: str):
        return SimpleNamespace(id=mod_id, package_type=PACKAGE_UMML_ASSETS)

    def test_ready_record_drops_stale_error_label_and_failed_key(self):
        app = _Probe({"repaired": False})
        key = ("repaired", "1", "meta", "source")
        app._auto_prepare_failures.add(key)
        app._auto_prepare_error_messages["repaired"] = "old failure"

        self.assertEqual(app._mod_status(self._record("repaired")), "ready")
        self.assertNotIn("repaired", app._auto_prepare_error_messages)
        self.assertNotIn(key, app._auto_prepare_failures)

    def test_pending_record_keeps_current_failure_visible(self):
        app = _Probe({"pending": True})
        key = ("pending", "1", "meta", "source")
        app._auto_prepare_failures.add(key)
        app._auto_prepare_error_messages["pending"] = "decoder failed"

        self.assertEqual(
            app._mod_status(self._record("pending")),
            "automatic preparation issue",
        )
        self.assertEqual(app._auto_prepare_error_messages["pending"], "decoder failed")
        self.assertIn(key, app._auto_prepare_failures)

    def test_reconcile_keeps_only_records_that_still_need_work(self):
        app = _Probe({"pending": True, "ready": False})
        pending_key = ("pending", "1", "meta", "source")
        ready_key = ("ready", "1", "meta", "source")
        removed_key = ("removed", "1", "meta", "source")
        app._auto_prepare_failures.update(
            {pending_key, ready_key, removed_key}
        )
        app._auto_prepare_error_messages.update(
            {
                "pending": "still broken",
                "ready": "already fixed",
                "removed": "no longer installed",
            }
        )

        app._reconcile_auto_prepare_failures(
            [self._record("pending"), self._record("ready")]
        )

        self.assertEqual(
            app._auto_prepare_error_messages,
            {"pending": "still broken"},
        )
        self.assertEqual(app._auto_prepare_failures, {pending_key})

    def test_scheduled_callback_is_cancelled_when_root_is_destroyed(self):
        app = _Probe({})
        app.root = _AfterRoot()
        app._closing = False

        app._schedule_auto_prepare_scan(delay=1)
        self.assertEqual(app._auto_prepare_after_id, "after-1")
        self.assertEqual(app.root.bound[0], "<Destroy>")

        app._auto_prepare_root_destroyed(SimpleNamespace(widget=app.root))

        self.assertEqual(app.root.cancelled, ["after-1"])
        self.assertIsNone(app._auto_prepare_after_id)
        self.assertFalse(app._auto_prepare_scan_scheduled)


if __name__ == "__main__":
    unittest.main()

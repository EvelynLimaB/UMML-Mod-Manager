import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

try:
    from PIL import Image  # noqa: F401
except ImportError:  # Legacy-only validation intentionally installs no manager deps.
    Image = None

if Image is not None:
    from umml_manager.gui import ManagerGUI
    from umml_manager.models import ModRecord, Profile
    from umml_manager.resolver import Resolution
    from umml_manager.ui_button_actions import ButtonStateActions
    from umml_manager.ui_library_actions import LibraryActions


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWidget:
    def __init__(self, **options):
        self.options = dict(options)

    def configure(self, **kwargs):
        self.options.update(kwargs)

    def cget(self, name):
        return self.options.get(name)


class FakeTree:
    def __init__(self, selected=()):
        self.selected = tuple(selected)

    def selection(self):
        return self.selected


@unittest.skipUnless(Image is not None, "Pillow is a manager-only dependency")
class ManagerButtonStateTests(unittest.TestCase):
    def _app(self, *, selected=True, enabled=True, blockers=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        meta = root / "meta.db"
        dat = root / "dat"
        game = root / "game"
        meta.write_bytes(b"db")
        dat.mkdir()
        game.mkdir()

        mod = ModRecord(
            "mod-a",
            "Mod A",
            package_type="umml-assets",
            prepared_path=str(root / "prepared"),
            prepared_against="fingerprint",
            files={"aa/hash": "0" * 64},
        )
        profile = Profile("Default", ["mod-a", "mod-b"] if enabled else ["mod-b"])
        resolution = Resolution(profile="Default")
        if blockers:
            resolution.unprepared.append("blocked")
        app = object.__new__(ManagerGUI)
        app._closing = False
        app._busy = False
        app._game_running = False
        app._gb_install_enabled = True
        app._gb_install_text = "Install"
        app._gb_can_previous = True
        app._gb_can_next = True
        app.meta_path = FakeVar(str(meta))
        app.dat_path = FakeVar(str(dat))
        app.game_dir = FakeVar(str(game))
        app.metadata_fingerprint = FakeVar("fingerprint")
        app.installation_key = FakeVar("steam-global")
        app.region = FakeVar("global")
        app.profile_name = FakeVar("Default")
        app.gb_selected = None
        app.gb_results = {}
        app.local_candidates = {}
        app.profile = lambda: profile
        app.current_resolution = lambda: resolution
        app.store = SimpleNamespace(get_mod=lambda mod_id: mod if mod_id == mod.id else None)

        selected_values = (mod.id,) if selected else ()
        library_buttons = {
            name: FakeWidget()
            for name in (
                "new_profile_button",
                "search_button",
                "import_folder_button",
                "import_archive_button",
                "preview_conflicts_button",
                "toggle_button",
                "move_up_button",
                "move_down_button",
                "prepare_button",
                "workspace_button",
                "remove_button",
                "apply_button",
            )
        }
        app.library = SimpleNamespace(
            tree=FakeTree(selected_values),
            selected_id=lambda: selected_values[0] if selected_values else None,
            profile_box=FakeWidget(),
            search_entry=FakeWidget(),
            **library_buttons,
        )

        discover_widgets = {
            name: FakeWidget()
            for name in (
                "gb_region_box",
                "gb_sort_box",
                "gb_query_entry",
                "browse_button",
                "open_gb_button",
                "install_gb_button",
                "prev_button",
                "next_button",
                "scan_roots_entry",
                "add_folder_button",
                "scan_button",
                "open_local_button",
                "import_local_button",
            )
        }
        app.discover = SimpleNamespace(**discover_widgets)
        app.selected_local_candidate = lambda: None

        settings_widgets = {
            name: FakeWidget()
            for name in (
                "autodetect_button",
                "dat_browse_button",
                "meta_browse_button",
                "game_browse_button",
                "save_button",
                "bind_profile_button",
                "diagnostics_button",
                "open_data_button",
                "open_workspaces_button",
                "region_box",
            )
        }
        app.settings = SimpleNamespace(**settings_widgets)
        app.sidebar_diagnostics_button = FakeWidget()
        app.refresh_plan_button = FakeWidget()
        app.studio = SimpleNamespace(
            tool_buttons={"full": FakeWidget(), "database": FakeWidget()},
            tool_mutating={"full": True, "database": True},
        )
        return app, mod, profile

    def test_no_selection_disables_selection_actions(self):
        app, _mod, _profile = self._app(selected=False)
        app.refresh_action_states()
        self.assertEqual(app.library.toggle_button.options["state"], "disabled")
        self.assertEqual(app.library.prepare_button.options["state"], "disabled")
        self.assertEqual(app.library.workspace_button.options["state"], "disabled")
        self.assertEqual(app.library.remove_button.options["state"], "disabled")

    def test_selected_enabled_mod_gets_contextual_controls(self):
        app, _mod, _profile = self._app(selected=True, enabled=True)
        app.refresh_action_states()
        self.assertEqual(app.library.toggle_button.options["text"], "Disable")
        self.assertEqual(app.library.move_up_button.options["state"], "disabled")
        self.assertEqual(app.library.move_down_button.options["state"], "normal")
        self.assertEqual(app.library.prepare_button.options["text"], "Re-prepare")
        self.assertEqual(app.library.prepare_button.options["state"], "normal")
        self.assertEqual(app.library.apply_button.options["state"], "normal")

    def test_game_running_blocks_apply_and_entire_legacy_studio(self):
        app, _mod, _profile = self._app()
        app._game_running = True
        app.refresh_action_states()
        self.assertEqual(app.library.apply_button.options["state"], "disabled")
        self.assertEqual(app.library.apply_button.options["text"], "Close game to apply")
        self.assertEqual(app.studio.tool_buttons["database"].options["state"], "disabled")
        self.assertEqual(app.studio.tool_buttons["database"].options["text"], "Close game first")
        self.assertEqual(app.studio.tool_buttons["full"].options["state"], "disabled")
        self.assertEqual(app.studio.tool_buttons["full"].options["text"], "Close game first")

    def test_busy_state_disables_mutating_and_network_actions(self):
        app, _mod, _profile = self._app()
        app.gb_selected = SimpleNamespace(id=123)
        app.gb_results = {"123": app.gb_selected}
        app._busy = True
        app.refresh_action_states()
        self.assertEqual(app.library.import_archive_button.options["state"], "disabled")
        self.assertEqual(app.discover.browse_button.options["state"], "disabled")
        self.assertEqual(app.discover.install_gb_button.options["state"], "disabled")
        self.assertEqual(app.settings.autodetect_button.options["state"], "disabled")
        self.assertEqual(app.studio.tool_buttons["database"].options["state"], "disabled")

    def test_gamebanana_and_paging_states_restore_after_task(self):
        app, _mod, _profile = self._app()
        app.gb_selected = SimpleNamespace(id=123)
        app.gb_results = {"123": app.gb_selected}
        app.refresh_action_states()
        self.assertEqual(app.discover.install_gb_button.options["state"], "normal")
        self.assertEqual(app.discover.prev_button.options["state"], "normal")
        self.assertEqual(app.discover.next_button.options["state"], "normal")

    def test_blocked_profile_explains_disabled_apply(self):
        app, _mod, _profile = self._app(blockers=True)
        app.refresh_action_states()
        self.assertEqual(app.library.apply_button.options["state"], "disabled")
        self.assertEqual(app.library.apply_button.options["text"], "Fix blockers to apply")


@unittest.skipUnless(Image is not None, "Pillow is a manager-only dependency")
class ButtonWrapperBehaviorTests(unittest.TestCase):
    def test_changed_browse_query_resets_to_first_page(self):
        class BrowseBase:
            def browse_gamebanana(self):
                self.calls += 1
                return self.gb_page

        class Harness(ButtonStateActions, BrowseBase):
            pass

        harness = Harness()
        harness.gb_region = FakeVar("global")
        harness.gb_sort = FakeVar("updated")
        harness.gb_query = FakeVar("first")
        harness.gb_page = 4
        harness.calls = 0

        self.assertEqual(harness.browse_gamebanana(), 1)
        harness.gb_page = 2
        self.assertEqual(harness.browse_gamebanana(), 2)
        harness.gb_query.set("second")
        self.assertEqual(harness.browse_gamebanana(), 1)
        self.assertEqual(harness.calls, 3)

    def test_unknown_game_status_is_fail_closed(self):
        class StatusBase:
            def _refresh_game_status(self):
                self.game_status.set("Game status unknown")

        class Harness(ButtonStateActions, StatusBase):
            def refresh_action_states(self):
                self.refreshed = True

        harness = Harness()
        harness.game_status = FakeVar()
        harness._game_running = False
        harness.refreshed = False
        harness._refresh_game_status()
        self.assertTrue(harness._game_running)
        self.assertTrue(harness.refreshed)
        self.assertEqual(
            harness.game_status.get(),
            "Game status unknown; writes blocked",
        )

    def test_typed_target_change_clears_stale_verification(self):
        saved = {
            "dat_path": "/old/dat",
            "meta_path": "/old/meta.db",
            "game_dir": "/old/game",
            "region": "global",
            "installation_key": "steam-global",
            "metadata_fingerprint": "old-fingerprint",
        }

        class Store:
            def load_settings(self):
                return dict(saved)

        class SaveBase:
            def save_settings(self, silent=False):
                self.saved = {
                    "installation_key": self.installation_key.get(),
                    "metadata_fingerprint": self.metadata_fingerprint.get(),
                    "silent": silent,
                }
                return self.saved

        class Harness(ButtonStateActions, SaveBase):
            pass

        harness = Harness()
        harness.store = Store()
        harness.dat_path = FakeVar("/new/dat")
        harness.meta_path = FakeVar("/old/meta.db")
        harness.game_dir = FakeVar("/old/game")
        harness.region = FakeVar("global")
        harness.installation_key = FakeVar("steam-global")
        harness.metadata_fingerprint = FakeVar("old-fingerprint")
        harness.installation_status = FakeVar("Using saved installation paths.")

        result = harness.save_settings(silent=True)
        self.assertEqual(result["installation_key"], "")
        self.assertEqual(result["metadata_fingerprint"], "")
        self.assertIn("Auto-detect again", harness.installation_status.get())

    def test_detected_target_save_preserves_new_verification(self):
        class Store:
            def load_settings(self):
                return {
                    "dat_path": "/old/dat",
                    "meta_path": "/old/meta.db",
                    "game_dir": "/old/game",
                    "region": "global",
                    "installation_key": "steam-global",
                    "metadata_fingerprint": "old",
                }

        class SaveBase:
            def save_settings(self, silent=False):
                return (
                    self.installation_key.get(),
                    self.metadata_fingerprint.get(),
                )

        class Harness(ButtonStateActions, SaveBase):
            pass

        harness = Harness()
        harness.store = Store()
        harness.dat_path = FakeVar("/new/dat")
        harness.meta_path = FakeVar("/new/meta.db")
        harness.game_dir = FakeVar("/new/game")
        harness.region = FakeVar("global")
        harness.installation_key = FakeVar("steam-global-new")
        harness.metadata_fingerprint = FakeVar("new")
        harness.installation_status = FakeVar("Detected Steam Global. Metadata is ready.")
        harness._saving_detected_installation = True

        self.assertEqual(
            harness.save_settings(),
            ("steam-global-new", "new"),
        )

    def test_manual_edit_after_detection_clears_stale_verification(self):
        class Store:
            def load_settings(self):
                return {
                    "dat_path": "/detected/dat",
                    "meta_path": "/detected/meta.db",
                    "game_dir": "/detected/game",
                    "region": "global",
                    "installation_key": "steam-global",
                    "metadata_fingerprint": "old",
                }

        class SaveBase:
            def save_settings(self, silent=False):
                return (
                    self.installation_key.get(),
                    self.metadata_fingerprint.get(),
                )

        class Harness(ButtonStateActions, SaveBase):
            pass

        harness = Harness()
        harness.store = Store()
        harness.dat_path = FakeVar("/manually-edited/dat")
        harness.meta_path = FakeVar("/detected/meta.db")
        harness.game_dir = FakeVar("/detected/game")
        harness.region = FakeVar("global")
        harness.installation_key = FakeVar("steam-global")
        harness.metadata_fingerprint = FakeVar("old")
        harness.installation_status = FakeVar(
            "Detected Steam Global. Metadata is ready."
        )
        harness._saving_detected_installation = False

        self.assertEqual(harness.save_settings(), ("", ""))
        self.assertIn("Auto-detect again", harness.installation_status.get())

    def test_profile_edits_preserve_existing_installation_binding(self):
        saved = []

        class Store:
            def save_profile(self, profile):
                saved.append(profile)

        harness = SimpleNamespace(
            store=Store(),
            region=FakeVar("global"),
            installation_key=FakeVar("steam-global-new"),
        )
        profile = Profile(
            "Japan",
            ["mod-a"],
            region="japan",
            installation_key="steam-japan",
        )

        LibraryActions._save_profile(harness, profile)

        self.assertEqual(saved, [profile])
        self.assertEqual(profile.region, "japan")
        self.assertEqual(profile.installation_key, "steam-japan")

    def test_profile_rebind_is_an_explicit_verified_target_action(self):
        saved = []
        profile = Profile("Portable", ["mod-a"], region="japan")

        class Store:
            def save_profile(self, value):
                saved.append(value)

        harness = SimpleNamespace(
            root=None,
            store=Store(),
            profile=lambda: profile,
            region=FakeVar("global"),
            installation_key=FakeVar("steam-global"),
            status=FakeVar(),
            refresh=lambda: None,
        )

        LibraryActions.rebind_profile(harness)

        self.assertEqual(saved, [profile])
        self.assertEqual(profile.region, "global")
        self.assertEqual(profile.installation_key, "steam-global")
        self.assertIn("Bound Portable", harness.status.get())


if __name__ == "__main__":
    unittest.main()

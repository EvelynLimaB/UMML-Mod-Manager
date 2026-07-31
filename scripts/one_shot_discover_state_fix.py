#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Patch anchor missing in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    gui = ROOT / "umml_manager/gui.py"
    replace_once(
        gui,
        "        self._auto_network_enabled = auto_network\n",
        "        self._auto_network_enabled = auto_network\n"
        "        self._current_page = \"library\"\n",
    )
    replace_once(
        gui,
        "        page.tkraise()\n        self.page_title.set(key.title())\n",
        "        self._current_page = key\n"
        "        page.tkraise()\n"
        "        self.page_title.set(key.title())\n",
    )
    replace_once(
        gui,
        "            enabled=selected_gb and self._gb_install_enabled and not busy,\n",
        "            enabled=(\n"
        "                selected_gb\n"
        "                and self._gb_install_enabled\n"
        "                and not discover_busy\n"
        "            ),\n",
    )
    replace_once(
        gui,
        "            enabled=self._gb_can_previous and not busy,\n",
        "            enabled=self._gb_can_previous and not discover_busy,\n",
    )
    replace_once(
        gui,
        "            enabled=self._gb_can_next and not busy,\n",
        "            enabled=self._gb_can_next and not discover_busy,\n",
    )

    experience = ROOT / "umml_manager/ui_discover_experience.py"
    text = experience.read_text(encoding="utf-8")
    marker = "    def gamebanana_filter_changed(self) -> None:\n"
    helper = (
        "    def _set_discover_status(self, message: str) -> None:\n"
        "        if getattr(self, \"_current_page\", \"\") == \"discover\":\n"
        "            self.status.set(message)\n\n"
    )
    if marker not in text:
        raise SystemExit("Discover status helper anchor missing")
    text = text.replace(marker, helper + marker, 1)
    replacements = {
        '        self.status.set("Refreshing the GameBanana catalogue…")\n':
            '        self._set_discover_status("Refreshing the GameBanana catalogue…")\n',
        '            self.status.set(f"{len(self.gb_results)} GameBanana mod(s) loaded{suffix}")\n':
            '            self._set_discover_status(\n'
            '                f"{len(self.gb_results)} GameBanana mod(s) loaded{suffix}"\n'
            '            )\n',
        '            self.status.set(\n                "GameBanana has not loaded yet. Refresh to retry; local imports still work."\n            )\n':
            '            self._set_discover_status(\n'
            '                "GameBanana has not loaded yet. Refresh to retry; local imports still work."\n'
            '            )\n',
        '        self.status.set("Loading the latest GameBanana mods automatically…")\n':
            '        self._set_discover_status(\n'
            '            "Loading the latest GameBanana mods automatically…"\n'
            '        )\n',
        '        self.status.set("Refreshing the GameBanana catalogue…")\n':
            '        self._set_discover_status("Refreshing the GameBanana catalogue…")\n',
        '            self.status.set(\n                f"Loaded {len(page.mods)} GameBanana mod(s) · updated {self._gb_loaded_at}"\n            )\n':
            '            self._set_discover_status(\n'
            '                f"Loaded {len(page.mods)} GameBanana mod(s) · updated {self._gb_loaded_at}"\n'
            '            )\n',
        '            self.status.set("GameBanana returned no matching mods")\n':
            '            self._set_discover_status("GameBanana returned no matching mods")\n',
        '            self.status.set(\n                "Could not refresh GameBanana; keeping the current results. " + message\n            )\n':
            '            self._set_discover_status(\n'
            '                "Could not refresh GameBanana; keeping the current results. " + message\n'
            '            )\n',
        '            self.status.set(\n                "GameBanana could not be reached; no local or game files changed"\n            )\n':
            '            self._set_discover_status(\n'
            '                "GameBanana could not be reached; no local or game files changed"\n'
            '            )\n',
    }
    for old, new in replacements.items():
        if old not in text:
            raise SystemExit(f"Discover status patch anchor missing: {old[:100]!r}")
        text = text.replace(old, new, 1)
    experience.write_text(text, encoding="utf-8")

    test = ROOT / "tests/test_manager_discover_experience.py"
    text = test.read_text(encoding="utf-8")
    anchor = "    def test_smoke_mode_disables_background_network(self):\n"
    addition = '''    def test_background_status_only_updates_inside_discover(self):
        actions = DiscoverExperienceActions()
        events = []
        actions.status = type("Status", (), {"set": lambda _self, value: events.append(value)})()
        actions._current_page = "library"
        actions._set_discover_status("hidden")
        actions._current_page = "discover"
        actions._set_discover_status("visible")
        self.assertEqual(events, ["visible"])

'''
    if anchor not in text:
        raise SystemExit("Discover state test anchor missing")
    test.write_text(text.replace(anchor, addition + anchor, 1), encoding="utf-8")


if __name__ == "__main__":
    main()

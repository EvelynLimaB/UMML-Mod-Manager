import json
import tempfile
import unittest
from pathlib import Path

from umml_manager.models import ModRecord
from umml_manager.ui_manifest_editor import (
    _ensure_workspace_manifest,
    _workspace_base_identity,
)


class ManagerManifestEditorTests(unittest.TestCase):
    def test_manifestless_import_gets_editable_modern_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            (workspace / "assets").mkdir(parents=True)
            record = ModRecord(
                id="creator.legacy",
                name="Legacy package",
                version="2",
                author="Creator",
                description="Imported without umml-mod.json",
                regions=["global"],
                targets={"characters": ["Special Week"]},
                tags=["costume"],
                dependencies=["creator.base"],
                load_after=["creator.base"],
                compatibility_notes="Use after the shared base.",
            )
            path = _ensure_workspace_manifest(workspace, record)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["id"], record.id)
            self.assertEqual(manifest["mod_version"], "2")
            self.assertEqual(manifest["targets"]["characters"], ["Special Week"])
            self.assertEqual(manifest["dependencies"], ["creator.base"])
            self.assertEqual(manifest["load_after"], ["creator.base"])

    def test_existing_manifest_values_are_not_replaced_by_record_defaults(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            path = workspace / "umml-mod.json"
            path.write_text(
                json.dumps(
                    {
                        "id": "creator.custom",
                        "title": "Workspace title",
                        "mod_version": "3",
                        "targets": {"characters": ["Silence Suzuka"]},
                    }
                ),
                encoding="utf-8",
            )
            record = ModRecord(
                id="creator.base",
                name="Record title",
                version="1",
                targets={"characters": ["Special Week"]},
            )
            _ensure_workspace_manifest(workspace, record)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["id"], "creator.custom")
            self.assertEqual(manifest["title"], "Workspace title")
            self.assertEqual(manifest["targets"]["characters"], ["Silence Suzuka"])

    def test_workspace_marker_exposes_base_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            (workspace / ".umml-workspace.json").write_text(
                json.dumps(
                    {
                        "base_mod_id": "creator.base",
                        "base_version": "1.0",
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                _workspace_base_identity(workspace),
                ("creator.base", "1.0"),
            )


if __name__ == "__main__":
    unittest.main()

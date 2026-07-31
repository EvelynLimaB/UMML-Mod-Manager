#!/usr/bin/env python3
"""Static structural audit for the Uma Mod Manager source tree.

This deliberately uses only the Python standard library so every contributor and
CI runner can execute it before packaging. It does not pretend to replace tests
or a type checker. It guards a small set of architectural, security, and visible
UI wiring rules whose accidental violation would be expensive.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (ROOT / "umml_manager",)
ENTRY_POINTS = (ROOT / "umml_manager_packaged.py",)
UI_FILES = {
    ROOT / "umml_manager/gui.py",
    ROOT / "umml_manager/ui_library.py",
    ROOT / "umml_manager/ui_discover.py",
    ROOT / "umml_manager/ui_settings.py",
    ROOT / "umml_manager/ui_studio.py",
    ROOT / "umml_manager/ui_mod_options.py",
    ROOT / "umml_manager/ui_package_builder.py",
    ROOT / "umml_manager/ui_manifest_editor.py",
}
ACTION_CLASS_NAMES = {
    "ManagerGUI",
    "AutoPrepareActions",
    "MaintenanceActions",
    "ButtonStateActions",
    "LibraryActions",
    "DiscoverActions",
    "SystemActions",
    "ModOptionsDialog",
    "PackageBuilderDialog",
    "ManifestEditorDialog",
}
WIDGET_METHOD_CALLBACKS = {"destroy"}

FORBIDDEN_CALLS = {
    "eval": "dynamic eval is not permitted",
    "exec": "dynamic exec is not permitted",
    "os.system": "use subprocess with an argument list",
    "pickle.load": "manager state and downloads are untrusted",
    "pickle.loads": "manager state and downloads are untrusted",
    "yaml.load": "use yaml.safe_load for untrusted mod metadata",
    "shutil.unpack_archive": "archive extraction must use the bounded store extractor",
    "tarfile.extractall": "archive extraction must use the bounded store extractor",
    "zipfile.extractall": "archive extraction must use the bounded store extractor",
}

LAYER_RULES = {
    "umml_manager.models": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.manifest": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.options": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.package_builder": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.safety": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.locking": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.engine": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.deployment": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.resolver": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.store": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
    "umml_manager.library": {"tkinter", "umml_manager.gui", "umml_manager.providers"},
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    message: str

    def render(self) -> str:
        return f"{self.path.relative_to(ROOT)}:{self.line}: {self.message}"


def source_files() -> list[Path]:
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    files.extend(path for path in ENTRY_POINTS if path.is_file())
    return sorted(set(files))


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    return ".".join(relative.parts)


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def imported_modules(tree: ast.AST, current: str) -> set[str]:
    result: set[str] = set()
    package = current.rsplit(".", 1)[0] if "." in current else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".") if package else []
                trim = max(0, node.level - 1)
                if trim:
                    base_parts = base_parts[:-trim]
                prefix = ".".join(base_parts)
                imported = ".".join(part for part in (prefix, node.module or "") if part)
            else:
                imported = node.module or ""
            if imported:
                result.add(imported)
    return result


def audit_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, SyntaxError, UnicodeError) as exc:
        line = getattr(exc, "lineno", 1) or 1
        return [Finding(path, line, f"could not parse source: {exc}")]

    current = module_name(path)
    forbidden_imports = LAYER_RULES.get(current, set())
    for imported in imported_modules(tree, current):
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in forbidden_imports):
            findings.append(
                Finding(path, 1, f"architecture violation: {current} imports {imported}")
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(Finding(path, node.lineno, "bare except is not permitted"))
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            reason = FORBIDDEN_CALLS.get(name)
            if reason:
                findings.append(Finding(path, node.lineno, f"forbidden call {name}: {reason}"))
            if name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output"}:
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        findings.append(
                            Finding(path, node.lineno, "subprocess shell=True is not permitted")
                        )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _has_mutable_default(node.args.defaults + node.args.kw_defaults):
                findings.append(
                    Finding(path, node.lineno, f"mutable default argument in {node.name}")
                )

    findings.extend(_duplicate_definitions(path, tree))
    return findings


def _has_mutable_default(defaults: Iterable[ast.expr | None]) -> bool:
    return any(isinstance(node, (ast.List, ast.Dict, ast.Set)) for node in defaults if node is not None)


def _duplicate_definitions(path: Path, tree: ast.Module) -> list[Finding]:
    findings: list[Finding] = []
    top_level: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            previous = top_level.get(node.name)
            if previous is not None:
                findings.append(
                    Finding(path, node.lineno, f"duplicate top-level definition {node.name!r}; first at line {previous}")
                )
            top_level[node.name] = node.lineno
        if isinstance(node, ast.ClassDef):
            methods: dict[str, int] = {}
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    previous = methods.get(child.name)
                    if previous is not None:
                        findings.append(
                            Finding(
                                path,
                                child.lineno,
                                f"duplicate method {node.name}.{child.name}; first at line {previous}",
                            )
                        )
                    methods[child.name] = child.lineno
    return findings


def _is_callback_owner(node: ast.ClassDef) -> bool:
    """Return whether a class may legitimately own a visible UI callback.

    Page and dialog classes often own small local actions such as opening help,
    exporting a report, or applying a filter. Action mixins and ManagerGUI own
    application-wide operations. Treating page methods as missing encouraged
    hiding valid callbacks inside lambdas, which made the audit quieter rather
    than the code safer.
    """

    return (
        node.name in ACTION_CLASS_NAMES
        or node.name.endswith("Page")
        or node.name.endswith("Dialog")
        or node.name.endswith("Window")
    )


def _action_methods(files: list[Path]) -> set[str]:
    methods: set[str] = set(WIDGET_METHOD_CALLBACKS)
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and _is_callback_owner(node):
                methods.update(
                    child.name
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
    return methods


def _callback_name(value: ast.expr) -> str:
    candidate = value.body if isinstance(value, ast.Lambda) else value
    if isinstance(candidate, ast.Call):
        candidate = candidate.func
    if (
        isinstance(candidate, ast.Attribute)
        and isinstance(candidate.value, ast.Name)
        and candidate.value.id in {"app", "self"}
    ):
        return candidate.attr
    return ""


def audit_button_callbacks(files: list[Path]) -> list[Finding]:
    methods = _action_methods(files)
    findings: list[Finding] = []
    for path in sorted(UI_FILES):
        if not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or dotted_name(node.func) not in {
                "ttk.Button",
                "tk.Button",
            }:
                continue
            command = next(
                (keyword.value for keyword in node.keywords if keyword.arg == "command"),
                None,
            )
            if command is None:
                findings.append(Finding(path, node.lineno, "visible button has no command callback"))
                continue
            callback = _callback_name(command)
            if callback and callback not in methods:
                findings.append(
                    Finding(
                        path,
                        node.lineno,
                        f"button callback {callback!r} is not implemented by ManagerGUI, a page, a dialog, or an action mixin",
                    )
                )
    return findings


def main() -> int:
    files = source_files()
    findings = [finding for path in files for finding in audit_file(path)]
    findings.extend(audit_button_callbacks(files))
    if findings:
        print("Uma Mod Manager source audit failed:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding.render()}", file=sys.stderr)
        return 1
    print(
        f"Uma Mod Manager source audit passed for {len(files)} Python files, "
        "including visible button callbacks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

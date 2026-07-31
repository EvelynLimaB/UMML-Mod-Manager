# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parents[1]

datas = [
    (str(ROOT / "UMML_data"), "UMML_data"),
    (str(ROOT / "MANAGER_VERSION"), "."),
    (str(ROOT / "MANAGER_README.md"), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "NOTICE.md"), "."),
    (str(ROOT / "CITATION.cff"), "."),
    (str(ROOT / "docs" / "PROJECT_VISION.md"), "docs"),
    (str(ROOT / "docs" / "BRANDING_AND_COMPATIBILITY.md"), "docs"),
    (str(ROOT / "docs" / "MOD_CREATOR_GUIDE.md"), "docs"),
    (str(ROOT / "docs" / "MANAGER_MOD_MANIFEST.md"), "docs"),
    (str(ROOT / "docs" / "MANAGER_ARCHITECTURE.md"), "docs"),
    (str(ROOT / "docs" / "MANAGER_DEVELOPMENT.md"), "docs"),
    (str(ROOT / "docs" / "MANAGER_AUDIT.md"), "docs"),
    (str(ROOT / "docs" / "MANAGER_FEATURE_ROADMAP.md"), "docs"),
    (str(ROOT / "docs" / "UMAEXTRACTOR_INTEGRATION.md"), "docs"),
    (str(ROOT / "docs" / "PACKAGING.md"), "docs"),
    (str(ROOT / "docs" / "TESTING_AND_FEEDBACK.md"), "docs"),
    (str(ROOT / "docs" / "RELEASE_PROCESS.md"), "docs"),
    (
        str(ROOT / "docs" / "releases" / "0.2.0-alpha.19.md"),
        "docs/releases",
    ),
]
binaries = []
hiddenimports = [
    "UMML",
    "UMML_core",
    "umml_platform",
    "umml_autodetect",
    "umml_manager.backends",
    "umml_manager.extractor_packages",
    "umml_manager.legacy_host",
    "umml_manager.locking",
    "umml_manager.network",
    "umml_manager.platform_bridge",
    "umml_manager.preview_images",
    "umml_manager.providers.base",
    "umml_manager.providers.gamebanana_previews",
    "umml_manager.safety",
    "umml_manager.support_bundle",
    "umml_manager.ui_discover",
    "umml_manager.ui_discover_actions",
    "umml_manager.ui_library",
    "umml_manager.ui_library_actions",
    "umml_manager.ui_settings",
    "umml_manager.ui_studio",
    "umml_manager.ui_support_bundle",
    "umml_manager.ui_system_actions",
    "umml_manager.ui_theme",
    "umml_manager.ui_veteran_external",
    "umml_manager.ui_veterans",
    "umml_manager.ui_veterans_window",
    "umml_manager.veterans",
]
for package in ("UnityPy", "apsw", "yaml", "vdf", "certifi", "PIL"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

analysis = Analysis(
    [str(ROOT / "umml_manager_packaged.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="umml-manager-bin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="umml-manager",
)

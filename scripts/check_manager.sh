#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m compileall -q \
  umml_manager \
  umml_manager_packaged.py \
  tests \
  scripts/audit_manager.py \
  scripts/audit_branding.py

python3 scripts/audit_manager.py
python3 scripts/audit_branding.py
python3 -m unittest discover -s tests -p 'test_manager*.py' -v
python3 scripts/test_manager_autodetect_runtime.py -- \
  python3 -m umml_manager

bash -n \
  install-manager.sh \
  uninstall-manager.sh \
  scripts/build_manager_frozen.sh \
  scripts/build_manager_deb.sh \
  scripts/build_manager_appimage.sh \
  scripts/manager_main_gate.sh \
  scripts/test_manager_source_install.sh \
  scripts/check_manager.sh

bash scripts/test_manager_source_install.sh

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate \
    packaging/linux/io.github.evelynlimab.ummlmanager.desktop \
    packaging/appimage/io.github.evelynlimab.ummlmanager.desktop
else
  printf 'Skipping desktop-file validation: desktop-file-validate not installed.\n' >&2
fi

if command -v appstream-util >/dev/null 2>&1; then
  appstream-util validate-relax \
    packaging/linux/io.github.evelynlimab.ummlmanager.metainfo.xml
else
  printf 'Skipping AppStream validation: appstream-util not installed.\n' >&2
fi

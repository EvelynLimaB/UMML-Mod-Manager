#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m py_compile \
  UMML.py UMML_core.py umml_platform.py umml_packaged.py \
  umml_autodetect/*.py

mapfile -t LEGACY_TEST_FILES < <(
  find tests -maxdepth 1 -type f -name 'test_*.py' \
    ! -name 'test_manager*.py' \
    ! -name 'test_import_automation.py' \
    -print | sort
)
LEGACY_TEST_MODULES=()
for path in "${LEGACY_TEST_FILES[@]}"; do
  module="${path%.py}"
  LEGACY_TEST_MODULES+=("${module//\//.}")
done
if ((${#LEGACY_TEST_MODULES[@]} == 0)); then
  printf 'No legacy regression tests were discovered.\n' >&2
  exit 1
fi
python3 -m unittest -v "${LEGACY_TEST_MODULES[@]}"

bash -n \
  install.sh uninstall.sh \
  scripts/build_release.sh \
  scripts/build_frozen.sh \
  scripts/build_deb.sh \
  scripts/build_appimage.sh \
  scripts/check_legacy.sh

scripts/build_release.sh

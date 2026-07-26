#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$ROOT/build/manager-frozen}"
WORK_DIR="${PYINSTALLER_MANAGER_WORK_DIR:-$ROOT/build/pyinstaller-manager-work}"
SPEC="$ROOT/packaging/pyinstaller/umml-manager.spec"
VERSION="$(tr -d '[:space:]' < "$ROOT/MANAGER_VERSION")"

[[ -n "$VERSION" ]] || { echo "MANAGER_VERSION is empty" >&2; exit 1; }
python3 -c 'import PyInstaller' >/dev/null 2>&1 || {
  echo "PyInstaller is missing. Install requirements-build.txt first." >&2
  exit 1
}

rm -rf "$OUT_DIR" "$WORK_DIR"
mkdir -p "$OUT_DIR" "$WORK_DIR"
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$OUT_DIR" \
  --workpath "$WORK_DIR" \
  "$SPEC"

BUNDLE="$OUT_DIR/umml-manager"
BINARY="$BUNDLE/umml-manager-bin"
[[ -x "$BINARY" ]] || { echo "Frozen UMML Manager executable was not created" >&2; exit 1; }
ACTUAL_VERSION="$("$BINARY" --version)"
[[ "$ACTUAL_VERSION" == "$VERSION" ]] || {
  echo "Frozen manager version mismatch: expected $VERSION, got $ACTUAL_VERSION" >&2
  exit 1
}
"$BINARY" cli --help >/dev/null
"$BINARY" cli self-test >/dev/null

printf 'Built frozen UMML Manager runtime: %s\n' "$BUNDLE"

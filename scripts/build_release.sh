#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
[[ -n "$VERSION" ]] || { echo "VERSION is empty" >&2; exit 1; }

OUT_DIR="${1:-$ROOT/dist}"
NAME="UMML-${VERSION}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
mkdir -p \
  "$OUT_DIR" \
  "$STAGE/$NAME/docs" \
  "$STAGE/$NAME/UMML_data" \
  "$STAGE/$NAME/assets" \
  "$STAGE/$NAME/scripts" \
  "$STAGE/$NAME/packaging/pyinstaller" \
  "$STAGE/$NAME/packaging/linux" \
  "$STAGE/$NAME/packaging/appimage"

for file in UMML.py UMML_core.py umml_platform.py umml_packaged.py \
            umml_manager_packaged.py requirements.txt requirements-build.txt \
            VERSION MANAGER_VERSION README.md MANAGER_README.md \
            CHANGELOG.md MANAGER_CHANGELOG.md RELEASE_NOTES.md SECURITY.md \
            CONTRIBUTING.md LICENSE; do
  install -m 0644 "$ROOT/$file" "$STAGE/$NAME/$file"
done

for doc in README.md LINUX.md AUTODETECTION.md MANAGER_ARCHITECTURE.md \
           MANAGER_DEVELOPMENT.md MANAGER_RELEASE_CHECKLIST.md PACKAGING.md; do
  install -m 0644 "$ROOT/docs/$doc" "$STAGE/$NAME/docs/$doc"
done

mkdir -p "$STAGE/$NAME/umml_autodetect" "$STAGE/$NAME/umml_manager/providers"
find "$ROOT/umml_autodetect" -maxdepth 1 -type f -name '*.py' -exec install -m 0644 {} "$STAGE/$NAME/umml_autodetect/" \;
find "$ROOT/umml_manager" -maxdepth 1 -type f -name '*.py' -exec install -m 0644 {} "$STAGE/$NAME/umml_manager/" \;
find "$ROOT/umml_manager/providers" -maxdepth 1 -type f -name '*.py' -exec install -m 0644 {} "$STAGE/$NAME/umml_manager/providers/" \;

install -m 0644 "$ROOT/UMML_data/dropdown.json" "$STAGE/$NAME/UMML_data/dropdown.json"
install -m 0644 "$ROOT/assets/umml.svg" "$STAGE/$NAME/assets/umml.svg"
install -m 0644 "$ROOT/assets/umml-manager.svg" "$STAGE/$NAME/assets/umml-manager.svg"
install -m 0755 "$ROOT/install.sh" "$STAGE/$NAME/install.sh"
install -m 0755 "$ROOT/uninstall.sh" "$STAGE/$NAME/uninstall.sh"
install -m 0755 "$ROOT/install-manager.sh" "$STAGE/$NAME/install-manager.sh"
install -m 0755 "$ROOT/uninstall-manager.sh" "$STAGE/$NAME/uninstall-manager.sh"

for script in build_release.sh build_frozen.sh build_deb.sh build_appimage.sh \
              build_manager_frozen.sh build_manager_deb.sh build_manager_appimage.sh \
              check_legacy.sh check_manager.sh check_all.sh; do
  install -m 0755 "$ROOT/scripts/$script" "$STAGE/$NAME/scripts/$script"
done

install -m 0644 "$ROOT/packaging/pyinstaller/umml.spec" \
  "$STAGE/$NAME/packaging/pyinstaller/umml.spec"
install -m 0644 "$ROOT/packaging/pyinstaller/umml-manager.spec" \
  "$STAGE/$NAME/packaging/pyinstaller/umml-manager.spec"
for metadata in \
  io.github.evelynlimab.umml.desktop \
  io.github.evelynlimab.umml.metainfo.xml \
  io.github.evelynlimab.ummlmanager.desktop \
  io.github.evelynlimab.ummlmanager.metainfo.xml; do
  install -m 0644 "$ROOT/packaging/linux/$metadata" \
    "$STAGE/$NAME/packaging/linux/$metadata"
done
install -m 0644 \
  "$ROOT/packaging/appimage/io.github.evelynlimab.ummlmanager.desktop" \
  "$STAGE/$NAME/packaging/appimage/io.github.evelynlimab.ummlmanager.desktop"

rm -f "$OUT_DIR/$NAME.zip" "$OUT_DIR/$NAME.tar.gz" "$OUT_DIR/SHA256SUMS"
(
  cd "$STAGE"
  python3 - "$NAME" "$OUT_DIR/$NAME.zip" <<'PY'
from pathlib import Path
import sys
import zipfile

root = Path(sys.argv[1])
out = Path(sys.argv[2])
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            archive.write(path, path.as_posix())
PY
  tar -czf "$OUT_DIR/$NAME.tar.gz" "$NAME"
)
(
  cd "$OUT_DIR"
  sha256sum "$NAME.zip" "$NAME.tar.gz" > SHA256SUMS
)
printf 'Built source release artifacts in %s\n' "$OUT_DIR"

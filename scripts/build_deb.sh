#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="${1:-$ROOT/build/frozen/umml}"
OUT_DIR="${2:-$ROOT/dist}"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
PACKAGE="umml-linux"
ARCH="amd64"
BUILD_ROOT="$ROOT/build/deb/${PACKAGE}_${VERSION}_${ARCH}"
PAYLOAD="$BUILD_ROOT/usr/lib/umml"
DESKTOP_ID="io.github.evelynlimab.umml"

[[ -x "$BUNDLE/umml" ]] || { echo "Frozen bundle not found: $BUNDLE" >&2; exit 1; }
command -v dpkg-deb >/dev/null 2>&1 || { echo "dpkg-deb is required" >&2; exit 1; }

rm -rf "$BUILD_ROOT"
mkdir -p \
  "$BUILD_ROOT/DEBIAN" \
  "$PAYLOAD" \
  "$BUILD_ROOT/usr/bin" \
  "$BUILD_ROOT/usr/share/applications" \
  "$BUILD_ROOT/usr/share/icons/hicolor/scalable/apps" \
  "$BUILD_ROOT/usr/share/metainfo" \
  "$BUILD_ROOT/usr/share/doc/$PACKAGE"
cp -a "$BUNDLE/." "$PAYLOAD/"

cat > "$BUILD_ROOT/usr/bin/umml" <<'LAUNCHER'
#!/usr/bin/env bash
set -Eeuo pipefail
cd /usr/lib/umml
exec /usr/lib/umml/umml "$@"
LAUNCHER
cat > "$BUILD_ROOT/usr/bin/umml-doctor" <<'DOCTOR'
#!/usr/bin/env bash
set -Eeuo pipefail
exec /usr/bin/umml --doctor
DOCTOR
chmod 0755 "$BUILD_ROOT/usr/bin/umml" "$BUILD_ROOT/usr/bin/umml-doctor"

install -m 0644 "$ROOT/packaging/linux/$DESKTOP_ID.desktop" \
  "$BUILD_ROOT/usr/share/applications/$DESKTOP_ID.desktop"
install -m 0644 "$ROOT/assets/umml.svg" \
  "$BUILD_ROOT/usr/share/icons/hicolor/scalable/apps/$DESKTOP_ID.svg"
install -m 0644 "$ROOT/packaging/linux/$DESKTOP_ID.metainfo.xml" \
  "$BUILD_ROOT/usr/share/metainfo/$DESKTOP_ID.metainfo.xml"
install -m 0644 "$ROOT/LICENSE" "$BUILD_ROOT/usr/share/doc/$PACKAGE/copyright"
install -m 0644 "$ROOT/README.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/README.md"
install -m 0644 "$ROOT/CHANGELOG.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/changelog"
gzip -n -9 "$BUILD_ROOT/usr/share/doc/$PACKAGE/changelog"

INSTALLED_SIZE="$(du -sk "$BUILD_ROOT/usr" | awk '{print $1}')"
cat > "$BUILD_ROOT/DEBIAN/control" <<EOF_CONTROL
Package: $PACKAGE
Version: $VERSION
Section: games
Priority: optional
Architecture: $ARCH
Maintainer: EvelynLimaB <lara_f@id.uff.br>
Installed-Size: $INSTALLED_SIZE
Depends: libc6 (>= 2.35), libx11-6, libxext6, libxrender1, libxcb1, libfontconfig1, libfreetype6, zlib1g
Homepage: https://github.com/EvelynLimaB/Uma-Mod-Manager
Description: Original UMML compatibility loader for Umamusume
 UMML loads, previews, backs up, and restores Umamusume Pretty Derby mods.
 This preserved compatibility package includes a self-contained Python runtime.
 New mod-manager and creator-tool development lives in Uma Mod Manager.
EOF_CONTROL

cat > "$BUILD_ROOT/DEBIAN/postinst" <<'EOF_POSTINST'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
exit 0
EOF_POSTINST
cat > "$BUILD_ROOT/DEBIAN/postrm" <<'EOF_POSTRM'
#!/bin/sh
set -e
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
exit 0
EOF_POSTRM
chmod 0755 "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/postrm"

mkdir -p "$OUT_DIR"
OUTPUT="$OUT_DIR/${PACKAGE}_${VERSION}_${ARCH}.deb"
rm -f "$OUTPUT"
dpkg-deb --root-owner-group --build "$BUILD_ROOT" "$OUTPUT"
dpkg-deb --info "$OUTPUT" >/dev/null
CONTENTS="$(mktemp)"
trap 'rm -f "$CONTENTS"' EXIT
dpkg-deb --contents "$OUTPUT" > "$CONTENTS"
grep -q 'usr/bin/umml$' "$CONTENTS"
rm -f "$CONTENTS"
trap - EXIT
printf 'Built original UMML compatibility package: %s\n' "$OUTPUT"

#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="${1:-$ROOT/build/manager-frozen/umml-manager}"
OUT_DIR="${2:-$ROOT/dist}"
VERSION="$(tr -d '[:space:]' < "$ROOT/MANAGER_VERSION")"
# Keep the technical package identifier stable so existing installations upgrade
# in place and continue using the same state, desktop ID, and recovery paths.
PACKAGE="umml-manager"
ARCH="amd64"
BUILD_ROOT="$ROOT/build/deb/${PACKAGE}_${VERSION}_${ARCH}"
PAYLOAD="$BUILD_ROOT/usr/lib/umml-manager"
DESKTOP_ID="io.github.evelynlimab.ummlmanager"

[[ -n "$VERSION" ]] || { echo "MANAGER_VERSION is empty" >&2; exit 1; }
[[ -x "$BUNDLE/umml-manager-bin" ]] || {
  echo "Frozen manager bundle not found: $BUNDLE" >&2
  echo "Run scripts/build_manager_frozen.sh first." >&2
  exit 1
}
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

cat > "$BUILD_ROOT/usr/bin/umml-manager" <<'EOF_GUI'
#!/usr/bin/env bash
set -Eeuo pipefail
cd /usr/lib/umml-manager
exec /usr/lib/umml-manager/umml-manager-bin gui "$@"
EOF_GUI
cat > "$BUILD_ROOT/usr/bin/umml-manager-cli" <<'EOF_CLI'
#!/usr/bin/env bash
set -Eeuo pipefail
cd /usr/lib/umml-manager
exec /usr/lib/umml-manager/umml-manager-bin cli "$@"
EOF_CLI
chmod 0755 "$BUILD_ROOT/usr/bin/umml-manager" "$BUILD_ROOT/usr/bin/umml-manager-cli"

install -m 0644 "$ROOT/packaging/linux/$DESKTOP_ID.desktop" \
  "$BUILD_ROOT/usr/share/applications/$DESKTOP_ID.desktop"
install -m 0644 "$ROOT/assets/umml-manager.svg" \
  "$BUILD_ROOT/usr/share/icons/hicolor/scalable/apps/$DESKTOP_ID.svg"
install -m 0644 "$ROOT/packaging/linux/$DESKTOP_ID.metainfo.xml" \
  "$BUILD_ROOT/usr/share/metainfo/$DESKTOP_ID.metainfo.xml"
install -m 0644 "$ROOT/LICENSE" "$BUILD_ROOT/usr/share/doc/$PACKAGE/copyright"
install -m 0644 "$ROOT/NOTICE.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/NOTICE.md"
install -m 0644 "$ROOT/README.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/README.md"
install -m 0644 "$ROOT/MANAGER_README.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/MANAGER_README.md"
install -m 0644 "$ROOT/CONTRIBUTING.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/CONTRIBUTING.md"
install -m 0644 "$ROOT/docs/BRANDING_AND_COMPATIBILITY.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/BRANDING_AND_COMPATIBILITY.md"
install -m 0644 "$ROOT/docs/MANAGER_ARCHITECTURE.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/MANAGER_ARCHITECTURE.md"
install -m 0644 "$ROOT/docs/MANAGER_DEVELOPMENT.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/MANAGER_DEVELOPMENT.md"
install -m 0644 "$ROOT/docs/PACKAGING.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/PACKAGING.md"
install -m 0644 "$ROOT/docs/TESTING_AND_FEEDBACK.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/TESTING_AND_FEEDBACK.md"
install -m 0644 "$ROOT/docs/RELEASE_PROCESS.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/RELEASE_PROCESS.md"
install -m 0644 "$ROOT/docs/releases/0.2.0-alpha.19.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/RELEASE_NOTES.md"
install -m 0644 "$ROOT/MANAGER_CHANGELOG.md" "$BUILD_ROOT/usr/share/doc/$PACKAGE/changelog"
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
Depends: libc6 (>= 2.35), libstdc++6, libx11-6, libxext6, libxrender1, libxcb1, libfontconfig1, libfreetype6, zlib1g
Homepage: https://github.com/EvelynLimaB/Uma-Mod-Manager
Description: Umamusume mod manager and creator toolkit
 Uma Mod Manager keeps imported mod versions immutable, prepares compatible
 packages automatically, resolves ordered profiles, and applies or restores
 game assets transactionally. It provides conflict previews, target-bound
 vanilla baselines, recovery journals, external-change protection, creator
 workspaces, compatibility metadata, GameBanana discovery, privacy-scrubbed
 tester support bundles, and guarded access to original UMML tools. The
 technical package name remains umml-manager so existing installations and
 user state upgrade in place.
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

(
  cd "$BUILD_ROOT"
  find usr -type f -print0 | sort -z | xargs -0 md5sum > DEBIAN/md5sums
)

mkdir -p "$OUT_DIR"
OUTPUT="$OUT_DIR/${PACKAGE}_${VERSION}_${ARCH}.deb"
rm -f "$OUTPUT"
dpkg-deb --root-owner-group --build "$BUILD_ROOT" "$OUTPUT"
dpkg-deb --info "$OUTPUT" >/dev/null
[[ "$(dpkg-deb --field "$OUTPUT" Package)" == "$PACKAGE" ]]
[[ "$(dpkg-deb --field "$OUTPUT" Version)" == "$VERSION" ]]
CONTENTS="$(mktemp)"
trap 'rm -f "$CONTENTS"' EXIT
dpkg-deb --contents "$OUTPUT" > "$CONTENTS"
grep -q 'usr/bin/umml-manager$' "$CONTENTS"
grep -q 'usr/bin/umml-manager-cli$' "$CONTENTS"
grep -q "usr/share/metainfo/$DESKTOP_ID.metainfo.xml$" "$CONTENTS"
grep -q 'usr/share/doc/umml-manager/NOTICE.md$' "$CONTENTS"
grep -q 'usr/share/doc/umml-manager/BRANDING_AND_COMPATIBILITY.md$' "$CONTENTS"
grep -q 'usr/share/doc/umml-manager/TESTING_AND_FEEDBACK.md$' "$CONTENTS"
grep -q 'usr/share/doc/umml-manager/RELEASE_PROCESS.md$' "$CONTENTS"
grep -q 'usr/share/doc/umml-manager/RELEASE_NOTES.md$' "$CONTENTS"
rm -f "$CONTENTS"
trap - EXIT

printf 'Built Uma Mod Manager Debian package: %s\n' "$OUTPUT"

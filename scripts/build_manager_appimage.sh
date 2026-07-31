#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE="${1:-$ROOT/build/manager-frozen/umml-manager}"
OUT_DIR="${2:-$ROOT/dist}"
VERSION="$(tr -d '[:space:]' < "$ROOT/MANAGER_VERSION")"
DISPLAY_VERSION="${VERSION//\~/-}"
ARCH="x86_64"
DESKTOP_ID="io.github.evelynlimab.ummlmanager"
BUILD_ROOT="$ROOT/build/appimage"
APPDIR="$BUILD_ROOT/UMML_Manager.AppDir"
TOOL_DIR="$ROOT/build/tools"
APPIMAGETOOL="${APPIMAGETOOL:-$TOOL_DIR/appimagetool-$ARCH.AppImage}"
APPIMAGETOOL_URL="${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage}"
# Pin the official AppImage/appimagetool continuous release asset. If upstream
# replaces it, fail deliberately until the new release asset is reviewed and
# this hash is updated from GitHub's published release digest.
APPIMAGETOOL_SHA256="${APPIMAGETOOL_SHA256:-a6d71e2b6cd66f8e8d16c37ad164658985e0cf5fcaa950c90a482890cb9d13e0}"
OUTPUT="$OUT_DIR/umml-manager_${DISPLAY_VERSION}_${ARCH}.AppImage"

[[ -n "$VERSION" ]] || { echo "MANAGER_VERSION is empty" >&2; exit 1; }
[[ "$DISPLAY_VERSION" != *"~"* ]] || {
  echo "Portable AppImage version still contains Debian's '~': $DISPLAY_VERSION" >&2
  exit 1
}
[[ -x "$BUNDLE/umml-manager-bin" ]] || {
  echo "Frozen manager bundle not found: $BUNDLE" >&2
  echo "Run scripts/build_manager_frozen.sh first." >&2
  exit 1
}

rm -rf "$APPDIR"
mkdir -p \
  "$APPDIR/usr/bin" \
  "$APPDIR/usr/lib/umml-manager" \
  "$APPDIR/usr/share/applications" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
  "$APPDIR/usr/share/metainfo" \
  "$APPDIR/usr/share/doc/umml-manager"
cp -a "$BUNDLE/." "$APPDIR/usr/lib/umml-manager/"

cat > "$APPDIR/usr/bin/umml-manager" <<'EOF_GUI'
#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec "$HERE/usr/lib/umml-manager/umml-manager-bin" gui "$@"
EOF_GUI
cat > "$APPDIR/usr/bin/umml-manager-cli" <<'EOF_CLI'
#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
exec "$HERE/usr/lib/umml-manager/umml-manager-bin" cli "$@"
EOF_CLI
chmod 0755 "$APPDIR/usr/bin/umml-manager" "$APPDIR/usr/bin/umml-manager-cli"

install -m 0644 \
  "$ROOT/packaging/appimage/$DESKTOP_ID.desktop" \
  "$APPDIR/usr/share/applications/$DESKTOP_ID.desktop"
install -m 0644 \
  "$ROOT/assets/umml-manager.svg" \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps/$DESKTOP_ID.svg"
install -m 0644 \
  "$ROOT/packaging/linux/$DESKTOP_ID.metainfo.xml" \
  "$APPDIR/usr/share/metainfo/$DESKTOP_ID.metainfo.xml"
install -m 0644 "$ROOT/LICENSE" "$APPDIR/usr/share/doc/umml-manager/copyright"
install -m 0644 "$ROOT/README.md" "$APPDIR/usr/share/doc/umml-manager/README.md"
install -m 0644 "$ROOT/MANAGER_README.md" "$APPDIR/usr/share/doc/umml-manager/MANAGER_README.md"
install -m 0644 "$ROOT/MANAGER_CHANGELOG.md" "$APPDIR/usr/share/doc/umml-manager/changelog"

cat > "$APPDIR/AppRun" <<'EOF_APPRUN'
#!/bin/sh
set -eu
APPDIR=${APPDIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}
export APPDIR
export PATH="$APPDIR/usr/bin${PATH:+:$PATH}"
export LD_LIBRARY_PATH="$APPDIR/usr/lib/umml-manager${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
BINARY="$APPDIR/usr/lib/umml-manager/umml-manager-bin"
case "${1-}" in
  --cli)
    shift
    exec "$BINARY" cli "$@"
    ;;
  cli|--legacy-host|--version|-V)
    exec "$BINARY" "$@"
    ;;
  *)
    exec "$BINARY" gui "$@"
    ;;
esac
EOF_APPRUN
chmod 0755 "$APPDIR/AppRun"

ln -s "usr/share/applications/$DESKTOP_ID.desktop" "$APPDIR/$DESKTOP_ID.desktop"
ln -s "usr/share/icons/hicolor/scalable/apps/$DESKTOP_ID.svg" "$APPDIR/$DESKTOP_ID.svg"
ln -s "$DESKTOP_ID.svg" "$APPDIR/.DirIcon"

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$APPDIR/usr/share/applications/$DESKTOP_ID.desktop"
fi
if command -v appstream-util >/dev/null 2>&1; then
  appstream-util validate-relax "$APPDIR/usr/share/metainfo/$DESKTOP_ID.metainfo.xml"
fi

mkdir -p "$TOOL_DIR" "$OUT_DIR"
if [[ ! -x "$APPIMAGETOOL" ]]; then
  tmp="$APPIMAGETOOL.download"
  rm -f "$tmp"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 3 --proto '=https' --tlsv1.2 \
      "$APPIMAGETOOL_URL" -o "$tmp"
  elif command -v wget >/dev/null 2>&1; then
    wget --https-only -O "$tmp" "$APPIMAGETOOL_URL"
  else
    echo "curl or wget is required to obtain appimagetool" >&2
    exit 1
  fi
  printf '%s  %s\n' "$APPIMAGETOOL_SHA256" "$tmp" | sha256sum -c -
  chmod 0755 "$tmp"
  mv "$tmp" "$APPIMAGETOOL"
else
  printf '%s  %s\n' "$APPIMAGETOOL_SHA256" "$APPIMAGETOOL" | sha256sum -c -
fi

rm -f "$OUTPUT"
ARCH="$ARCH" VERSION="$DISPLAY_VERSION" APPIMAGE_EXTRACT_AND_RUN=1 \
  "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"
chmod 0755 "$OUTPUT"

ACTUAL_VERSION="$(APPIMAGE_EXTRACT_AND_RUN=1 "$OUTPUT" --version)"
[[ "$ACTUAL_VERSION" == "$VERSION" ]] || {
  echo "AppImage version mismatch: expected $VERSION, got $ACTUAL_VERSION" >&2
  exit 1
}
APPIMAGE_EXTRACT_AND_RUN=1 "$OUTPUT" --cli --help >/dev/null

VERIFY_ROOT="$(mktemp -d)"
trap 'rm -rf "$VERIFY_ROOT"' EXIT
(
  cd "$VERIFY_ROOT"
  "$OUTPUT" --appimage-extract >/dev/null
)
diff -qr \
  "$BUNDLE" \
  "$VERIFY_ROOT/squashfs-root/usr/lib/umml-manager"
[[ -f "$VERIFY_ROOT/squashfs-root/usr/share/metainfo/$DESKTOP_ID.metainfo.xml" ]]
[[ -f "$VERIFY_ROOT/squashfs-root/usr/share/applications/$DESKTOP_ID.desktop" ]]
rm -rf "$VERIFY_ROOT"
trap - EXIT

sha256sum "$OUTPUT"
printf 'Built UMML Manager AppImage: %s\n' "$OUTPUT"

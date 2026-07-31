#!/usr/bin/env bash
set -Eeuo pipefail

XDG_DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$XDG_DATA_ROOT/umml-manager-app"
DATA_DIR="$XDG_DATA_ROOT/umml-manager"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$XDG_DATA_ROOT/applications"
ICON_ROOT="$XDG_DATA_ROOT/icons/hicolor"
SOURCE_DESKTOP_ID="io.github.evelynlimab.ummlmanager.source"
OLD_DESKTOP_ID="io.github.evelynlimab.ummlmanager"

rm -f "$BIN_DIR/umml-manager-source" "$BIN_DIR/umml-manager-source-cli"
for launcher in "$BIN_DIR/umml-manager" "$BIN_DIR/umml-manager-cli"; do
    if [[ -f "$launcher" ]] && grep -q "UMML_MANAGER_SOURCE_COMPAT" "$launcher"; then
        rm -f "$launcher"
    fi
done
rm -f "$DESKTOP_DIR/$SOURCE_DESKTOP_ID.desktop"
rm -f "$ICON_ROOT/scalable/apps/$SOURCE_DESKTOP_ID.svg"

# Remove only application code. The manager's library, profiles, settings,
# prepared files, baselines, transactions, downloads, and workspaces live in
# DATA_DIR and are intentionally retained.
rm -rf "$APP_DIR"

# Clean known files from the historical mixed app/data layout while preserving
# every manager state directory and JSON registry.
rm -rf "$DATA_DIR/umml_manager"
rm -f \
    "$DATA_DIR/UMML_core.py" \
    "$DATA_DIR/MANAGER_VERSION" \
    "$DATA_DIR/requirements.txt" \
    "$DATA_DIR/MANAGER_README.md" \
    "$DATA_DIR/MANAGER_CHANGELOG.md"

old_desktop="$DESKTOP_DIR/$OLD_DESKTOP_ID.desktop"
if [[ -f "$old_desktop" ]] && grep -Eq "Exec=($BIN_DIR/)?umml-manager|Path=$DATA_DIR" "$old_desktop"; then
    rm -f "$old_desktop"
fi

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -q -t -f "$ICON_ROOT" >/dev/null 2>&1 || true

printf 'UMML Manager source application files removed.\n'
printf 'Manager data was preserved at: %s\n' "$DATA_DIR"
printf 'The Debian package, if installed, was not modified.\n'

#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SMOKE_ROOT="$(mktemp -d)"
trap 'rm -rf -- "$SMOKE_ROOT"' EXIT

export HOME="$SMOKE_ROOT/home"
export XDG_DATA_HOME="$SMOKE_ROOT/data"
APP_DIR="$XDG_DATA_HOME/umml-manager-app"
DATA_DIR="$XDG_DATA_HOME/umml-manager"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$XDG_DATA_HOME/applications"
EXPECTED_VERSION="$(tr -d '[:space:]' < "$ROOT/MANAGER_VERSION")"

mkdir -p \
  "$HOME" \
  "$DATA_DIR/baseline" \
  "$DATA_DIR/sources/kept" \
  "$DATA_DIR/profiles-kept" \
  "$DATA_DIR/umml_manager" \
  "$DESKTOP_DIR"
printf 'preserve-baseline\n' > "$DATA_DIR/baseline/sentinel"
printf 'preserve-source\n' > "$DATA_DIR/sources/kept/sentinel"
printf 'historical-code\n' > "$DATA_DIR/umml_manager/stale.py"
printf 'historical-code\n' > "$DATA_DIR/UMML_core.py"
cat > "$DESKTOP_DIR/io.github.evelynlimab.ummlmanager.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Historical UMML Manager
Exec=$BIN_DIR/umml-manager
Path=$DATA_DIR
EOF

bash "$ROOT/install-manager.sh"

test -d "$APP_DIR/umml_manager"
test -d "$APP_DIR/umml_autodetect"
test -d "$APP_DIR/UMML_data"
test -f "$APP_DIR/UMML.py"
test -f "$APP_DIR/UMML_core.py"
test -f "$APP_DIR/umml_platform.py"
test -x "$BIN_DIR/umml-manager-source"
test -x "$BIN_DIR/umml-manager-source-cli"
test -x "$BIN_DIR/umml-manager"
test -x "$BIN_DIR/umml-manager-cli"
test "$("$BIN_DIR/umml-manager-source-cli" --version)" = "$EXPECTED_VERSION"
"$BIN_DIR/umml-manager-source-cli" self-test
"$BIN_DIR/umml-manager-source" --help >/dev/null

test ! -e "$DATA_DIR/umml_manager"
test ! -e "$DATA_DIR/UMML_core.py"
test ! -e "$DESKTOP_DIR/io.github.evelynlimab.ummlmanager.desktop"
test "$(cat "$DATA_DIR/baseline/sentinel")" = "preserve-baseline"
test "$(cat "$DATA_DIR/sources/kept/sentinel")" = "preserve-source"

bash "$ROOT/uninstall-manager.sh"

test ! -e "$APP_DIR"
test ! -e "$BIN_DIR/umml-manager-source"
test ! -e "$BIN_DIR/umml-manager-source-cli"
test ! -e "$BIN_DIR/umml-manager"
test ! -e "$BIN_DIR/umml-manager-cli"
test "$(cat "$DATA_DIR/baseline/sentinel")" = "preserve-baseline"
test "$(cat "$DATA_DIR/sources/kept/sentinel")" = "preserve-source"
test -d "$DATA_DIR/profiles-kept"

printf 'UMML Manager isolated source install/uninstall round trip passed.\n'

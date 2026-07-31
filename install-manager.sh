#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
XDG_DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$XDG_DATA_ROOT/umml-manager-app"
DATA_DIR="$XDG_DATA_ROOT/umml-manager"
OLD_APP_DIR="$DATA_DIR"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$XDG_DATA_ROOT/applications"
ICON_DIR="$XDG_DATA_ROOT/icons/hicolor/scalable/apps"
LEGACY_PYTHON="$XDG_DATA_ROOT/umml/env/bin/python"
SOURCE_LAUNCHER="$BIN_DIR/umml-manager-source"
SOURCE_CLI_LAUNCHER="$BIN_DIR/umml-manager-source-cli"
COMPAT_LAUNCHER="$BIN_DIR/umml-manager"
COMPAT_CLI_LAUNCHER="$BIN_DIR/umml-manager-cli"
DESKTOP_ID="io.github.evelynlimab.ummlmanager.source"
DESKTOP_FILE="$DESKTOP_DIR/$DESKTOP_ID.desktop"
OLD_DESKTOP_FILE="$DESKTOP_DIR/io.github.evelynlimab.ummlmanager.desktop"
ICON_FILE="$ICON_DIR/$DESKTOP_ID.svg"

fatal() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

[[ -d "$SOURCE_ROOT/umml_manager" ]] || fatal "umml_manager/ must be beside this installer."
[[ -d "$SOURCE_ROOT/umml_autodetect" ]] || fatal "umml_autodetect/ must be beside this installer."
[[ -d "$SOURCE_ROOT/UMML_data" ]] || fatal "UMML_data/ must be beside this installer."
[[ -f "$SOURCE_ROOT/UMML.py" ]] || fatal "UMML.py must be beside this installer."
[[ -f "$SOURCE_ROOT/UMML_core.py" ]] || fatal "UMML_core.py must be beside this installer."
[[ -f "$SOURCE_ROOT/umml_platform.py" ]] || fatal "umml_platform.py must be beside this installer."
[[ -f "$SOURCE_ROOT/MANAGER_VERSION" ]] || fatal "MANAGER_VERSION must be beside this installer."
[[ -f "$SOURCE_ROOT/assets/umml-manager.svg" ]] || fatal "Manager icon is missing."

if [[ -x "$LEGACY_PYTHON" ]]; then
    PYTHON="$LEGACY_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
else
    fatal "Python 3 is required. Install legacy UMML first or install Python 3 with Tk."
fi

"$PYTHON" - <<'PY' || fatal "The selected Python does not include Tkinter. Install legacy UMML first for its isolated environment."
import tkinter
print("Tk", tkinter.TkVersion)
PY

"$PYTHON" - <<'PY' || fatal "Pillow is required by the Manager interface. Install requirements.txt in the selected Python environment."
from PIL import Image, ImageTk
print("Pillow", Image.__version__)
PY

mkdir -p "$APP_DIR" "$DATA_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"
rm -rf "$APP_DIR/umml_manager" "$APP_DIR/umml_autodetect" "$APP_DIR/UMML_data"
cp -a "$SOURCE_ROOT/umml_manager" "$APP_DIR/umml_manager"
cp -a "$SOURCE_ROOT/umml_autodetect" "$APP_DIR/umml_autodetect"
cp -a "$SOURCE_ROOT/UMML_data" "$APP_DIR/UMML_data"
install -m 0644 "$SOURCE_ROOT/UMML.py" "$APP_DIR/UMML.py"
install -m 0644 "$SOURCE_ROOT/UMML_core.py" "$APP_DIR/UMML_core.py"
install -m 0644 "$SOURCE_ROOT/umml_platform.py" "$APP_DIR/umml_platform.py"
install -m 0644 "$SOURCE_ROOT/MANAGER_VERSION" "$APP_DIR/MANAGER_VERSION"
install -m 0644 "$SOURCE_ROOT/assets/umml-manager.svg" "$ICON_FILE"
[[ -f "$SOURCE_ROOT/requirements.txt" ]] && install -m 0644 "$SOURCE_ROOT/requirements.txt" "$APP_DIR/requirements.txt"
[[ -f "$SOURCE_ROOT/MANAGER_README.md" ]] && install -m 0644 "$SOURCE_ROOT/MANAGER_README.md" "$APP_DIR/MANAGER_README.md"
[[ -f "$SOURCE_ROOT/MANAGER_CHANGELOG.md" ]] && install -m 0644 "$SOURCE_ROOT/MANAGER_CHANGELOG.md" "$APP_DIR/MANAGER_CHANGELOG.md"

# Migrate the historical source layout without touching manager state, sources,
# profiles, baselines, transactions, workspaces, or downloads.
if [[ "$OLD_APP_DIR" != "$APP_DIR" ]]; then
    rm -rf "$OLD_APP_DIR/umml_manager"
    rm -f \
        "$OLD_APP_DIR/UMML_core.py" \
        "$OLD_APP_DIR/MANAGER_VERSION" \
        "$OLD_APP_DIR/requirements.txt" \
        "$OLD_APP_DIR/MANAGER_README.md" \
        "$OLD_APP_DIR/MANAGER_CHANGELOG.md"
fi

cat > "$SOURCE_LAUNCHER" <<EOF
#!/usr/bin/env bash
# UMML_MANAGER_SOURCE_LAUNCHER
set -Eeuo pipefail
cd "$APP_DIR"
exec "$PYTHON" -m umml_manager.gui "\$@"
EOF
chmod 0755 "$SOURCE_LAUNCHER"

cat > "$SOURCE_CLI_LAUNCHER" <<EOF
#!/usr/bin/env bash
# UMML_MANAGER_SOURCE_LAUNCHER
set -Eeuo pipefail
cd "$APP_DIR"
exec "$PYTHON" -m umml_manager "\$@"
EOF
chmod 0755 "$SOURCE_CLI_LAUNCHER"

# Compatibility commands prefer the independently packaged Debian application
# whenever it exists, preventing ~/.local/bin from shadowing /usr/bin.
cat > "$COMPAT_LAUNCHER" <<EOF
#!/usr/bin/env bash
# UMML_MANAGER_SOURCE_COMPAT
set -Eeuo pipefail
if [[ -x /usr/bin/umml-manager ]]; then
    exec /usr/bin/umml-manager "\$@"
fi
exec "$SOURCE_LAUNCHER" "\$@"
EOF
chmod 0755 "$COMPAT_LAUNCHER"

cat > "$COMPAT_CLI_LAUNCHER" <<EOF
#!/usr/bin/env bash
# UMML_MANAGER_SOURCE_COMPAT
set -Eeuo pipefail
if [[ -x /usr/bin/umml-manager-cli ]]; then
    exec /usr/bin/umml-manager-cli "\$@"
fi
exec "$SOURCE_CLI_LAUNCHER" "\$@"
EOF
chmod 0755 "$COMPAT_CLI_LAUNCHER"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=UMML Manager (Source)
GenericName=UM:PD Mod Manager
Comment=Run the source-installed UMML Manager
Exec=$SOURCE_LAUNCHER
Path=$APP_DIR
Terminal=false
Icon=$DESKTOP_ID
Categories=Game;Utility;
Keywords=UMML;Mod;Manager;Profiles;GameBanana;Steam;Proton;
StartupNotify=true
EOF
chmod 0644 "$DESKTOP_FILE"

# The historical source desktop file used the Debian application's desktop ID.
# Remove it only when it clearly belongs to the old per-user source install.
if [[ -f "$OLD_DESKTOP_FILE" ]] && grep -Eq "Exec=($BIN_DIR/)?umml-manager|Path=$OLD_APP_DIR" "$OLD_DESKTOP_FILE"; then
    rm -f "$OLD_DESKTOP_FILE"
fi

"$PYTHON" -m py_compile \
    "$APP_DIR"/UMML.py \
    "$APP_DIR"/UMML_core.py \
    "$APP_DIR"/umml_platform.py \
    "$APP_DIR"/umml_autodetect/*.py \
    "$APP_DIR"/umml_manager/*.py \
    "$APP_DIR"/umml_manager/providers/*.py
"$SOURCE_CLI_LAUNCHER" --version >/dev/null

if ! "$PYTHON" -c 'import certifi' >/dev/null 2>&1; then
    printf '\nWARNING: certifi is not installed in %s.\n' "$PYTHON" >&2
    printf 'GameBanana access will require a usable system CA bundle; install requirements.txt for the portable fallback.\n' >&2
fi

if "$PYTHON" - <<'PY'
import importlib
missing = []
for name in ("UnityPy", "yaml", "apsw", "vdf"):
    try:
        importlib.import_module(name)
    except Exception:
        missing.append(name)
if missing:
    raise SystemExit(", ".join(missing))
PY
then
    (
        cd "$APP_DIR"
        "$PYTHON" -c 'import UMML'
    ) || fatal "The installed legacy Studio runtime could not import UMML."
else
    printf '\nWARNING: asset preparation dependencies are missing in %s.\n' "$PYTHON" >&2
    printf 'The Manager GUI is installed, but preparation and legacy Studio require the complete requirements.txt environment.\n' >&2
fi

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -q -t -f "$XDG_DATA_ROOT/icons/hicolor" >/dev/null 2>&1 || true

printf '\nUMML Manager source installation completed.\n'
printf 'Source GUI: %s\nSource CLI: %s\n' "$SOURCE_LAUNCHER" "$SOURCE_CLI_LAUNCHER"
printf 'Manager data preserved at: %s\nVersion: %s\n' "$DATA_DIR" "$("$SOURCE_CLI_LAUNCHER" --version)"
if [[ -x /usr/bin/umml-manager ]]; then
    printf 'The generic umml-manager command now prefers the Debian package.\n'
fi

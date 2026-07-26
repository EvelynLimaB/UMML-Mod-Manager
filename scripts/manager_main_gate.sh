#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
MODE=""
APPIMAGE=""
CHECKSUMS=""
PROFILE="Default"
SKIP_PROFILE=0
OUTPUT=""

usage() {
    cat <<'EOF'
Usage:
  scripts/manager_main_gate.sh --appimage PATH --checksums PATH [--profile NAME]
  scripts/manager_main_gate.sh --installed [--profile NAME]
  scripts/manager_main_gate.sh --source [--profile NAME]

Options:
  --appimage PATH  Validate one UMML Manager AppImage.
  --checksums PATH Verify the AppImage against the workflow's SHA256SUMS file.
  --installed      Validate the installed umml-manager package.
  --source         Validate the current source checkout.
  --profile NAME   Real profile whose prepared payloads should be exercised on
                   disposable copies. Defaults to Default.
  --skip-profile   Run only non-profile gates. The final result is INCOMPLETE.
  --output PATH    New log path. Existing files are never overwritten.

The game must be closed. The script reads the real installation and Manager
state, but every deployment write is redirected to a temporary copy.
EOF
}

fatal() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 2
}

while (($#)); do
    case "$1" in
        --appimage)
            (($# >= 2)) || fatal "--appimage requires a path"
            [[ -z "$MODE" ]] || fatal "choose exactly one package mode"
            MODE="appimage"
            APPIMAGE="$2"
            shift 2
            ;;
        --installed)
            [[ -z "$MODE" ]] || fatal "choose exactly one package mode"
            MODE="installed"
            shift
            ;;
        --checksums)
            (($# >= 2)) || fatal "--checksums requires a path"
            CHECKSUMS="$2"
            shift 2
            ;;
        --source)
            [[ -z "$MODE" ]] || fatal "choose exactly one package mode"
            MODE="source"
            shift
            ;;
        --profile)
            (($# >= 2)) || fatal "--profile requires a name"
            PROFILE="$2"
            shift 2
            ;;
        --skip-profile)
            SKIP_PROFILE=1
            shift
            ;;
        --output)
            (($# >= 2)) || fatal "--output requires a path"
            OUTPUT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fatal "unknown option: $1"
            ;;
    esac
done

[[ -n "$MODE" ]] || {
    usage
    fatal "choose --appimage, --installed, or --source"
}
[[ -n "$PROFILE" ]] || fatal "profile name cannot be empty"
EXPECTED_VERSION="$(tr -d '[:space:]' < "$ROOT/MANAGER_VERSION")"
[[ -n "$EXPECTED_VERSION" ]] || fatal "MANAGER_VERSION is empty"

if [[ -z "$OUTPUT" ]]; then
    OUTPUT="$PWD/umml-manager-main-gate-$(date -u +%Y%m%dT%H%M%SZ).log"
fi
[[ ! -e "$OUTPUT" ]] || fatal "refusing to overwrite existing log: $OUTPUT"
mkdir -p "$(dirname -- "$OUTPUT")"
: > "$OUTPUT"

case "$MODE" in
    appimage)
        APPIMAGE="$(realpath -- "$APPIMAGE")"
        [[ -f "$APPIMAGE" && -x "$APPIMAGE" ]] || {
            fatal "AppImage is missing or not executable: $APPIMAGE"
        }
        [[ -n "$CHECKSUMS" ]] || {
            fatal "--checksums is required with --appimage"
        }
        CHECKSUMS="$(realpath -- "$CHECKSUMS")"
        [[ -f "$CHECKSUMS" ]] || {
            fatal "checksum file is missing: $CHECKSUMS"
        }
        CLI=(env APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE" --cli)
        GUI=(env APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE")
        PACKAGE_LABEL="$APPIMAGE"
        ;;
    installed)
        command -v umml-manager-cli >/dev/null 2>&1 || {
            fatal "umml-manager-cli is not installed"
        }
        command -v umml-manager >/dev/null 2>&1 || {
            fatal "umml-manager is not installed"
        }
        CLI=(umml-manager-cli)
        GUI=(umml-manager)
        PACKAGE_LABEL="$(command -v umml-manager-cli)"
        ;;
    source)
        cd "$ROOT" || fatal "could not enter source checkout"
        CLI=(python3 -m umml_manager)
        GUI=(python3 -m umml_manager.gui)
        PACKAGE_LABEL="$ROOT"
        ;;
esac

failures=0

note() {
    printf '%s\n' "$*" | tee -a "$OUTPUT"
}

run_gate() {
    local label="$1"
    shift
    note ""
    note "=== $label ==="
    "$@" 2>&1 | tee -a "$OUTPUT"
    local status=${PIPESTATUS[0]}
    if ((status == 0)); then
        note "[PASS] $label"
    else
        note "[FAIL] $label (exit $status)"
        failures=$((failures + 1))
    fi
}

repository_gate() {
    command -v git >/dev/null 2>&1 || {
        printf 'git is required to identify the candidate revision\n'
        return 1
    }
    local revision
    revision="$(git -C "$ROOT" rev-parse HEAD)" || return
    printf 'Revision: %s\n' "$revision"
    git -C "$ROOT" diff --quiet -- || {
        printf 'Tracked working-tree changes are present\n'
        return 1
    }
    git -C "$ROOT" diff --cached --quiet -- || {
        printf 'Staged changes are present\n'
        return 1
    }
}

package_version_gate() {
    local actual
    actual="$("${CLI[@]}" --version)" || return
    printf 'Expected: %s\nActual:   %s\n' "$EXPECTED_VERSION" "$actual"
    [[ "$actual" == "$EXPECTED_VERSION" ]]
}

appimage_checksum_gate() {
    local filename expected actual
    filename="$(basename -- "$APPIMAGE")"
    expected="$(
        awk -v filename="$filename" \
            '$2 == filename || $2 == "*" filename { print $1; exit }' \
            "$CHECKSUMS"
    )"
    [[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || {
        printf 'No valid checksum entry found for %s in %s\n' \
            "$filename" "$CHECKSUMS"
        return 1
    }
    actual="$(sha256sum "$APPIMAGE" | awk '{print $1}')" || return
    printf 'Expected: %s\nActual:   %s\n' "$expected" "$actual"
    [[ "${actual,,}" == "${expected,,}" ]]
}

note "UMML Manager main-promotion gate"
note "UTC: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
note "Mode: $MODE"
note "Target: $PACKAGE_LABEL"
note "Profile: $PROFILE"
if [[ -r /etc/os-release ]]; then
    note "OS: $(. /etc/os-release; printf '%s' "${PRETTY_NAME:-unknown}")"
fi
note "Kernel: $(uname -srmo)"

run_gate "Repository revision" repository_gate
run_gate "Package version" package_version_gate
if [[ "$MODE" == "appimage" ]]; then
    run_gate "AppImage workflow checksum" appimage_checksum_gate
fi
run_gate "Disposable deployment self-test" "${CLI[@]}" self-test
run_gate "Read-only Manager doctor" "${CLI[@]}" doctor
run_gate "Live GameBanana metadata and preview" \
    "${CLI[@]}" network-smoke --region global
run_gate "Native Tk page rendering" "${GUI[@]}" --smoke-test

if ((SKIP_PROFILE)); then
    note ""
    note "[INCOMPLETE] Real profile verification was explicitly skipped."
    failures=$((failures + 1))
else
    run_gate "Real profile on disposable game copies" \
        "${CLI[@]}" verify-profile "$PROFILE"
fi

note ""
if ((failures == 0)); then
    note "RESULT: PASS"
    note "All automated main-promotion gates passed."
    note "Real game and Manager state were read only; deployment writes used temporary copies."
else
    note "RESULT: FAIL ($failures gate(s) incomplete or failed)"
fi
note "Report: $OUTPUT"

exit "$((failures == 0 ? 0 : 1))"

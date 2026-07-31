from __future__ import annotations

import json
import os
import platform
import re
import stat
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .store import ManagerStore
from .validation import collect_manager_diagnostics
from .version import manager_version

SUPPORT_BUNDLE_SCHEMA_VERSION = 1
SUPPORT_BUNDLE_PREFIX = "uma-mod-manager-support"
MAX_MOD_SUMMARIES = 2_000
MAX_PROFILE_SUMMARIES = 500
MAX_TEXT_VALUE = 32_768
_PRIVATE_KEY_PARTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "cookie",
    "authorization",
    "viewerid",
    "username",
    "circlename",
    "email",
)


class SupportBundleError(RuntimeError):
    """Raised when a sanitized support bundle cannot be created safely."""


def default_support_bundle_name(now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    stamp = moment.strftime("%Y%m%dT%H%M%SZ")
    version = manager_version().replace("~", "-").replace("/", "-")
    return f"{SUPPORT_BUNDLE_PREFIX}-{version}-{stamp}.zip"


def create_support_bundle(
    store: ManagerStore,
    destination: str | Path,
    *,
    diagnostics_collector: Callable[[ManagerStore], dict[str, object]] = (
        collect_manager_diagnostics
    ),
    now: datetime | None = None,
) -> Path:
    """Create a small, inspectable, privacy-scrubbed support archive.

    The bundle intentionally excludes mod payloads, game assets, baselines,
    roster snapshots, raw settings, provider downloads, and transaction data.
    It contains only build/platform information, redacted diagnostics, and
    bounded high-level library/profile summaries useful for reproducing a report.
    """

    selected = Path(destination).expanduser()
    if selected.suffix.casefold() != ".zip":
        selected = selected.with_suffix(".zip")
    _validate_destination(selected)
    parent = selected.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / selected.name
    _validate_destination(target)

    moment = now or datetime.now(timezone.utc)
    settings, settings_error = _safe_settings(store)
    redactions = _redaction_map(store, settings)
    diagnostics = _safe_diagnostics(store, diagnostics_collector)
    mods, mod_total, mods_error = _safe_mod_summary(store)
    profiles, profile_total, profiles_error = _safe_profile_summary(store)

    warnings = [
        value
        for value in (settings_error, mods_error, profiles_error)
        if value
    ]
    if mod_total > len(mods):
        warnings.append(
            f"Included {len(mods)} of {mod_total} mod summaries; the report is bounded."
        )
    if profile_total > len(profiles):
        warnings.append(
            f"Included {len(profiles)} of {profile_total} profile summaries; the report is bounded."
        )

    report: dict[str, Any] = {
        "schema_version": SUPPORT_BUNDLE_SCHEMA_VERSION,
        "created_at": moment.isoformat(),
        "product": "Uma Mod Manager",
        "manager_version": manager_version(),
        "runtime": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "frozen": bool(getattr(sys, "frozen", False)),
        },
        "configuration": {
            "region": str(settings.get("region") or ""),
            "theme": str(settings.get("theme") or "system"),
            "profile": str(settings.get("profile") or "Default"),
            "game_directory_configured": bool(
                str(settings.get("game_dir") or "").strip()
            ),
            "data_directory_configured": bool(
                str(settings.get("dat_path") or "").strip()
            ),
            "metadata_configured": bool(
                str(settings.get("meta_path") or "").strip()
            ),
            "verified_installation_identity": bool(
                str(settings.get("installation_key") or "").strip()
            ),
            "metadata_fingerprint_recorded": bool(
                str(settings.get("metadata_fingerprint") or "").strip()
            ),
        },
        "library": {
            "count": mod_total,
            "included_summaries": len(mods),
            "mods": mods,
        },
        "profiles": {
            "count": profile_total,
            "included_summaries": len(profiles),
            "items": profiles,
        },
        "diagnostics": diagnostics,
        "warnings": warnings,
        "privacy": {
            "raw_settings_included": False,
            "mod_payloads_included": False,
            "game_assets_included": False,
            "baselines_included": False,
            "roster_data_included": False,
            "provider_downloads_included": False,
            "known_paths_and_private_keys_redacted": True,
            "text_values_bounded": True,
        },
    }
    report = _bound_and_redact(report, redactions)

    readme = _bundle_readme(target.name)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(
                "support-report.json",
                json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
                + "\n",
            )
            archive.writestr("README.txt", readme)
        os.replace(temporary_path, target)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise SupportBundleError(f"Could not create support bundle: {exc}") from exc

    return target


def _validate_destination(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    except OSError as exc:
        raise SupportBundleError(
            f"Could not inspect support bundle destination: {path}: {exc}"
        ) from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise SupportBundleError(
            f"Support bundle destination must be a regular file: {path}"
        )


def _safe_settings(store: ManagerStore) -> tuple[dict[str, Any], str]:
    try:
        return store.load_settings(repair=False), ""
    except Exception as exc:
        return {}, f"Settings could not be read: {exc}"


def _safe_diagnostics(
    store: ManagerStore,
    collector: Callable[[ManagerStore], dict[str, object]],
) -> dict[str, object]:
    try:
        return collector(store)
    except Exception as exc:
        return {
            "status": "failed",
            "ready": False,
            "checks": [],
            "error": str(exc),
        }


def _safe_mod_summary(
    store: ManagerStore,
) -> tuple[list[dict[str, Any]], int, str]:
    try:
        records = store.list_mods()
    except Exception as exc:
        return [], 0, f"Mod registry could not be summarized: {exc}"

    result: list[dict[str, Any]] = []
    for record in records[:MAX_MOD_SUMMARIES]:
        source = getattr(record, "source", None)
        result.append(
            {
                "id": str(getattr(record, "id", "")),
                "name": str(getattr(record, "name", "")),
                "version": str(getattr(record, "version", "")),
                "package_type": str(getattr(record, "package_type", "")),
                "prepared": bool(
                    getattr(record, "files", None)
                    and getattr(record, "prepared_path", "")
                ),
                "regions": list(getattr(record, "regions", ()) or ()),
                "source_provider": str(
                    getattr(source, "provider", "") if source is not None else ""
                ),
                "source_submission_id": str(
                    getattr(source, "submission_id", "")
                    if source is not None
                    else ""
                ),
                "source_file_id": str(
                    getattr(source, "file_id", "") if source is not None else ""
                ),
                "dependency_count": len(
                    getattr(record, "dependencies", ()) or ()
                ),
                "incompatibility_count": len(
                    getattr(record, "incompatibilities", ()) or ()
                ),
                "option_group_count": len(
                    getattr(record, "option_groups", ()) or ()
                ),
            }
        )
    return result, len(records), ""


def _safe_profile_summary(
    store: ManagerStore,
) -> tuple[list[dict[str, Any]], int, str]:
    try:
        profiles = store.list_profiles()
    except Exception as exc:
        return [], 0, f"Profile registry could not be summarized: {exc}"

    result = [
        {
            "name": str(getattr(profile, "name", "")),
            "enabled_mod_count": len(getattr(profile, "enabled", ()) or ()),
            "configured_mod_count": len(getattr(profile, "options", {}) or {}),
            "region": str(getattr(profile, "region", "")),
            "bound_to_verified_installation": bool(
                str(getattr(profile, "installation_key", "") or "").strip()
            ),
        }
        for profile in profiles[:MAX_PROFILE_SUMMARIES]
    ]
    return result, len(profiles), ""


def _redaction_map(
    store: ManagerStore,
    settings: dict[str, Any],
) -> list[tuple[str, str]]:
    candidates = [
        (str(Path.home()), "<HOME>"),
        (str(store.paths.root), "<MANAGER_ROOT>"),
        (str(settings.get("game_dir") or ""), "<GAME_DIR>"),
        (str(settings.get("dat_path") or ""), "<DAT_DIR>"),
        (str(settings.get("meta_path") or ""), "<META_PATH>"),
    ]
    unique: dict[str, str] = {}
    for raw, replacement in candidates:
        value = raw.strip()
        if value:
            unique[value] = replacement
            unique[value.replace("\\", "/")] = replacement
    return sorted(unique.items(), key=lambda item: len(item[0]), reverse=True)


def _bound_and_redact(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if any(part in normalized for part in _PRIVATE_KEY_PARTS):
                cleaned[str(key)] = "<redacted>"
            else:
                cleaned[str(key)] = _bound_and_redact(item, replacements)
        return cleaned
    if isinstance(value, list):
        return [_bound_and_redact(item, replacements) for item in value]
    if isinstance(value, tuple):
        return [_bound_and_redact(item, replacements) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        for raw, replacement in replacements:
            normalized = normalized.replace(raw.replace("\\", "/"), replacement)
        if len(normalized) > MAX_TEXT_VALUE:
            omitted = len(normalized) - MAX_TEXT_VALUE
            normalized = normalized[:MAX_TEXT_VALUE] + f"\n<truncated {omitted} characters>"
        return normalized
    return value


def _bundle_readme(filename: str) -> str:
    return f"""Uma Mod Manager tester support bundle

File: {filename}

This archive was generated for bug reports and testing feedback. It contains:
- a privacy-scrubbed support-report.json;
- build, platform, configuration-presence, library-summary, profile-summary,
  and read-only diagnostic information.

It intentionally does NOT contain:
- game assets or databases;
- mod payloads or downloaded archives;
- vanilla baselines or transaction contents;
- veteran-roster snapshots;
- raw settings, credentials, tokens, or known viewer/account fields.

Inspect support-report.json before uploading it. Redaction is deliberately
conservative, but no automatic filter can understand every custom path, mod
name, or free-form error message a person may consider private.

Attach this ZIP to the Testing feedback or Bug report issue form together with
exact reproduction steps. Do not attach copyrighted game files.
"""

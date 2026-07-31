from __future__ import annotations

import argparse
import json
from pathlib import Path

from .deployment import ApplyEngine
from .discovery import default_search_roots, scan_mod_candidates
from .legacy_adapter import LegacyAssetAdapter
from .models import Profile
from .providers.gamebanana_previews import PreviewGameBananaClient
from .resolver import Resolution, resolve_profile
from .safety import SafetyError, hash_file, validate_sha256
from .store import ManagerStore, StoreError, default_root
from .studio import LegacyToolLauncher
from .version import manager_version

REGIONS = ("global", "japan", "taiwan", "korea")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="umml-manager-cli")
    parser.add_argument(
        "--version",
        action="version",
        version=manager_version(),
    )
    parser.add_argument(
        "--root",
        default=str(default_root()),
        help="Manager data directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")

    self_test = sub.add_parser(
        "self-test",
        help="run a disposable import, deployment, restoration, and recovery test",
    )
    self_test.add_argument("--json", action="store_true")

    doctor = sub.add_parser(
        "doctor",
        help="run read-only platform, HTTPS, target, and Manager-state checks",
    )
    doctor.add_argument("--json", action="store_true")

    network_smoke = sub.add_parser(
        "network-smoke",
        help="verify live GameBanana browse, detail, file, and preview responses",
    )
    network_smoke.add_argument(
        "--region",
        choices=("global", "japan"),
        default="global",
    )
    network_smoke.add_argument("--json", action="store_true")

    verify = sub.add_parser(
        "verify-profile",
        help=(
            "apply and restore a real profile on disposable copies of its "
            "target files"
        ),
    )
    verify.add_argument("profile")
    verify.add_argument("--dat", default="")
    verify.add_argument("--game-dir", default="")
    verify.add_argument("--meta", default="")
    verify.add_argument("--region", choices=REGIONS, default="")
    verify.add_argument("--installation-key", default="")
    verify.add_argument("--json", action="store_true")

    imported = sub.add_parser("import")
    imported.add_argument("path")
    imported.add_argument("--id")

    scan = sub.add_parser("scan")
    scan.add_argument("paths", nargs="*")
    scan.add_argument("--depth", type=int, default=5)

    browse = sub.add_parser("browse")
    browse.add_argument(
        "--region",
        choices=("global", "japan"),
        default="global",
    )
    browse.add_argument("--page", type=int, default=1)
    browse.add_argument(
        "--sort",
        choices=("updated", "newest", "popular", "downloads", "views"),
        default="updated",
    )
    browse.add_argument("--query", default="")

    gamebanana = sub.add_parser("gamebanana")
    gamebanana.add_argument("url")
    gamebanana.add_argument("--file-id", type=int)

    prepare = sub.add_parser("prepare")
    prepare.add_argument("mod_id")
    prepare.add_argument("--meta", required=True)

    workspace = sub.add_parser("workspace")
    workspace.add_argument("mod_id")

    profile = sub.add_parser("profile")
    profile.add_argument("name")
    profile.add_argument("mods", nargs="*")
    profile.add_argument("--region", choices=REGIONS, default="")
    profile.add_argument("--installation-key", default="")

    plan = sub.add_parser("plan")
    plan.add_argument("profile")
    _add_target_options(plan, dat_required=False)

    apply_command = sub.add_parser("apply")
    apply_command.add_argument("profile")
    _add_target_options(apply_command, dat_required=True)
    apply_command.add_argument("--game-dir")
    apply_command.add_argument("--force", action="store_true")
    apply_command.add_argument(
        "--import-legacy-baselines",
        action="store_true",
        help=(
            "copy required originals from the sibling dat.backup folder before "
            "adopting files installed by legacy UMML"
        ),
    )

    updates = sub.add_parser("updates")
    updates.add_argument("mod_id", nargs="?")

    studio = sub.add_parser("studio")
    studio.add_argument("tool", nargs="?", default="full")
    studio.add_argument("--dat", default="")
    studio.add_argument("--game-dir", default="")
    studio.add_argument("--meta", default="")
    studio.add_argument("--region", default="global")
    return parser


def _add_target_options(
    parser: argparse.ArgumentParser,
    *,
    dat_required: bool,
) -> None:
    parser.add_argument("--region", choices=REGIONS, default="")
    parser.add_argument("--installation-key", default="")
    parser.add_argument(
        "--meta",
        default="",
        help=(
            "Prepared metadata DB used to reject stale prepared caches. "
            "Apply requires this path or a valid auto-detected saved metadata path."
        ),
    )
    if dat_required:
        parser.add_argument("--dat", required=True)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "self-test":
            from .validation import run_disposable_self_test

            report = run_disposable_self_test()
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                for check in report["checks"]:
                    print(f"[PASS] {check}")
                print(
                    "RESULT: PASS — disposable data only; "
                    "no real game files were changed"
                )
            return 0

        if args.command == "network-smoke":
            from .validation import run_live_network_smoke

            report = run_live_network_smoke(region=args.region)
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(
                    f"[PASS] GameBanana {report['region']}: "
                    f"{report['catalog_records']} catalog record(s); "
                    f"submission {report['submission_id']} exposed "
                    f"{report['downloadable_files']} file(s)"
                )
                print(
                    f"[PASS] Preview: {report['preview_content_type']}, "
                    f"{report['preview_bytes']} byte(s), "
                    f"{report['preview_size'][0]}×{report['preview_size'][1]}"
                )
                print(
                    "RESULT: PASS — verified live metadata and preview only; "
                    "nothing was downloaded into the library or game"
                )
            return 0

        store = ManagerStore(
            args.root,
            create=args.command not in {"doctor", "verify-profile"},
        )
        if args.command == "doctor":
            from .validation import collect_manager_diagnostics

            report = collect_manager_diagnostics(store)
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                for check in report["checks"]:
                    marker = "OK" if check["passed"] else "CHECK"
                    detail = str(check["detail"])
                    lines = detail.splitlines() or [""]
                    print(f"[{marker}] {check['name']}: {lines[0]}")
                    for line in lines[1:]:
                        print(f"    {line}")
                print(
                    "RESULT: "
                    + ("READY" if report["ready"] else "CHECK REQUIRED")
                )
            return 0 if report["ready"] else 2
        if args.command == "list":
            for mod in store.list_mods():
                status = (
                    "prepared"
                    if mod.files and mod.prepared_path
                    else "needs prepare"
                )
                print(
                    f"{mod.id}\t{mod.version}\t{mod.package_type}\t"
                    f"{status}\t{mod.name}"
                )
        elif args.command == "verify-profile":
            from .validation import verify_profile_on_disposable_copy

            settings = store.load_settings(repair=False)
            if store.settings_warning:
                raise StoreError(store.settings_warning)
            profile = store.get_profile(args.profile)
            dat_path = (
                str(args.dat).strip()
                or str(settings.get("dat_path", "")).strip()
            )
            if not dat_path:
                raise StoreError(
                    "Profile verification requires --dat or a saved detected "
                    "game data path"
                )
            game_dir = (
                str(args.game_dir).strip()
                or str(settings.get("game_dir", "")).strip()
            )
            fingerprint = _metadata_fingerprint(
                args.meta,
                store=store,
                settings=settings,
                required=True,
            )
            target_key = _target_installation_key(
                args.installation_key,
                store=store,
                dat_path=dat_path,
                settings=settings,
            )
            region = (
                str(args.region).strip()
                or profile.region
                or str(settings.get("region", "")).strip()
            )
            report = verify_profile_on_disposable_copy(
                store,
                profile,
                dat_path=dat_path,
                game_dir=game_dir or None,
                target_region=region,
                target_installation_key=target_key,
                metadata_fingerprint=fingerprint,
            )
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                print(
                    f"[PASS] {report['profile']}: verified "
                    f"{report['files']} winner(s), "
                    f"{report['conflicts']} conflict(s), "
                    f"{report['affected_files']} affected target(s)"
                )
                print(
                    "RESULT: PASS — applied and restored disposable copies; "
                    "real game and Manager state were unchanged"
                )
        elif args.command == "import":
            path = Path(args.path)
            record = (
                store.import_folder(path, mod_id=args.id)
                if path.is_dir()
                else store.import_archive(path, mod_id=args.id)
            )
            print(record.id)
        elif args.command == "scan":
            roots = [Path(item) for item in args.paths] or default_search_roots()
            for candidate in scan_mod_candidates(
                roots,
                max_depth=args.depth,
            ):
                print(
                    f"{candidate.kind}\t{candidate.confidence}\t"
                    f"{candidate.path}\t{candidate.reason}"
                )
        elif args.command == "browse":
            page = PreviewGameBananaClient().browse(
                region=args.region,
                page=args.page,
                sort=args.sort,
                query=args.query,
            )
            for mod in page.mods:
                print(
                    f"{mod.id}\t{mod.likes}\t{mod.downloads}\t"
                    f"{mod.author}\t{mod.name}"
                )
        elif args.command == "gamebanana":
            record = PreviewGameBananaClient().import_mod(
                store,
                args.url,
                file_id=args.file_id,
            )
            print(record.id)
        elif args.command == "prepare":
            record = LegacyAssetAdapter(store, args.meta).prepare(
                store.get_mod(args.mod_id)
            )
            print(f"Prepared {len(record.files)} assets for {record.id}")
        elif args.command == "workspace":
            print(store.create_workspace(args.mod_id))
        elif args.command == "profile":
            store.save_profile(
                Profile(
                    args.name,
                    list(args.mods),
                    region=args.region,
                    installation_key=args.installation_key,
                )
            )
            print(args.name)
        elif args.command in {"plan", "apply"}:
            profile = store.get_profile(args.profile)
            required = args.command == "apply"
            fingerprint = _metadata_fingerprint(
                args.meta,
                store=store,
                required=required,
            )
            target_key = _target_installation_key(
                args.installation_key,
                store=store,
                dat_path=args.dat if required else "",
            )
            resolution = resolve_profile(
                profile,
                store.list_mods(),
                target_region=args.region or profile.region,
                target_installation_key=target_key,
                metadata_fingerprint=fingerprint,
            )
            if args.command == "plan":
                print(json.dumps(_resolution_dict(resolution), indent=2))
            else:
                result = ApplyEngine(
                    store,
                    args.dat,
                    game_dir=args.game_dir,
                ).apply(
                    resolution,
                    force=args.force,
                    import_legacy_baselines=args.import_legacy_baselines,
                )
                print(
                    f"Installed {result.installed}; restored "
                    f"{result.restored}; unchanged {result.unchanged}; "
                    f"imported {result.imported_baselines} legacy baseline(s); "
                    f"recovered {result.recovered_transactions} interrupted "
                    "transaction(s)"
                )
        elif args.command == "updates":
            provider = PreviewGameBananaClient()
            records = (
                [store.get_mod(args.mod_id)]
                if args.mod_id
                else store.list_mods()
            )
            for record in records:
                update = provider.update_available(record)
                if update:
                    print(f"{record.id}\t{update.id}\t{update.name}")
        elif args.command == "studio":
            LegacyToolLauncher().launch(
                args.tool,
                dat_path=args.dat,
                game_dir=args.game_dir,
                meta_path=args.meta,
                region=args.region,
            )
        return 0
    except StoreError as exc:
        print(f"error: {exc}")
        return 2
    except Exception as exc:
        print(f"error: {exc}")
        return 1


def _metadata_fingerprint(
    value: str,
    *,
    store: ManagerStore | None = None,
    settings: dict | None = None,
    required: bool = False,
) -> str:
    if value:
        path = Path(value).expanduser()
        if not path.is_file():
            raise StoreError(f"Metadata database not found: {path}")
        return hash_file(path)

    current_settings = (
        settings
        if settings is not None
        else store.load_settings() if store is not None else {}
    )
    saved_meta = str(current_settings.get("meta_path", "")).strip()
    saved_path = Path(saved_meta).expanduser() if saved_meta else None
    if saved_path is not None and saved_path.is_file():
        recorded = str(
            current_settings.get("metadata_fingerprint", "")
        ).strip()
        if not recorded:
            if required:
                raise StoreError(
                    "Saved metadata has no verified fingerprint; pass --meta "
                    "explicitly or run installation auto-detection again"
                )
            return ""
        actual = hash_file(saved_path)
        try:
            expected = validate_sha256(recorded)
        except SafetyError as exc:
            raise StoreError(
                "Saved metadata fingerprint is invalid; run installation "
                "auto-detection again"
            ) from exc
        if actual != expected:
            raise StoreError(
                "Saved metadata changed since installation detection; run "
                "auto-detection and re-prepare affected mods"
            )
        return actual

    if required:
        raise StoreError(
            "Apply requires --meta or a valid auto-detected metadata database in "
            "manager settings"
        )
    return ""


def _target_installation_key(
    value: str,
    *,
    store: ManagerStore,
    dat_path: str = "",
    settings: dict | None = None,
) -> str:
    explicit = str(value or "").strip()
    if explicit:
        return explicit
    current_settings = (
        settings if settings is not None else store.load_settings()
    )
    saved_key = str(
        current_settings.get("installation_key", "")
    ).strip()
    if not saved_key:
        return ""
    if not dat_path:
        return saved_key
    saved_dat = str(current_settings.get("dat_path", "")).strip()
    if not saved_dat:
        return ""
    try:
        matches = (
            Path(saved_dat).expanduser().resolve()
            == Path(dat_path).expanduser().resolve()
        )
    except (OSError, ValueError):
        matches = False
    return saved_key if matches else ""


def _resolution_dict(resolution: Resolution) -> dict:
    return {
        "profile": resolution.profile,
        "target_region": resolution.target_region,
        "target_installation_key": resolution.target_installation_key,
        "metadata_fingerprint": resolution.metadata_fingerprint,
        "files": len(resolution.winners),
        "blocking": resolution.blocking_issues,
        "missing": resolution.missing,
        "unprepared": resolution.unprepared,
        "stale_prepared": resolution.stale_prepared,
        "unsupported": resolution.unsupported,
        "incompatible": resolution.incompatible,
        "wrong_installation": resolution.wrong_installation,
        "invalid": resolution.invalid,
        "missing_dependencies": resolution.missing_dependencies,
        "incompatibility_conflicts": resolution.incompatibility_conflicts,
        "duplicates": resolution.duplicates,
        "conflicts": [
            conflict.__dict__ for conflict in resolution.conflicts
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())

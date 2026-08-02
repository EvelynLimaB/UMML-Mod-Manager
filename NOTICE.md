# Project lineage and third-party notices

Uma Mod Manager is built on community work. This file records project lineage and integration boundaries; it does not replace the license text shipped by any component.

## UMML / UmaMusume Mod Loader

- Project: `tumugu/UmaMusume_Mod_Loader`
- Source: https://github.com/tumugu/UmaMusume_Mod_Loader
- Relationship: upstream project and compatibility-code lineage

The repository preserves upstream-derived loader, editor, asset, and platform behavior while moving new work into the tested `umml_manager` architecture. The existing repository [MIT license](LICENSE) and copyright notice remain intact.

## Veteran-data tools

Uma Mod Manager can import output from, or launch user-supplied copies of, projects in the community `umadump` / `UmaExtractor` lineage:

- `rockisch/umadump`: https://github.com/rockisch/umadump
- `NECOtype/UmaExtractor`: https://github.com/NECOtype/UmaExtractor
- `xancia/UmaExtractor`: https://github.com/xancia/UmaExtractor
- `Werseter/umadump`: https://github.com/Werseter/umadump

These projects retain their original authorship. Uma Mod Manager does not copy, build, bundle, modify, or redistribute extractor source or binaries unless a compatible project-wide license or explicit permission permits it. Importing an output format, installing a user-selected source archive locally, or launching a separately supplied tool does not relicense that project.

Standalone Manager packages include a narrow Python 3.14 host capable of running supported user-supplied Werseter source in a separate process. The host is Uma Mod Manager code; the Werseter source remains outside this repository and release payload.

A separate process is a fault and permission boundary, not a security sandbox. User-selected Python source still runs with the permissions of the current operating-system account and can access resources available to that account. Use only a trusted upstream archive and verify its provenance. The Manager validates the known package layout, dependency contract, archive structure, and execution arguments, but it cannot make arbitrary third-party Python harmless through administrative optimism.

## Python runtime

- Project: CPython
- Source: https://github.com/python/cpython
- Packaged version: `3.14.6`
- License: Python Software Foundation License Version 2 and associated historical notices
- Relationship: interpreter runtime embedded by PyInstaller for the application and private extractor host
- Modifications: none to CPython source

The full runtime license is shipped as `third_party/licenses/Python-3.14.6.txt` in source and inside finished packages.

## Minidump

- Project: `skelsec/minidump`
- Source: https://github.com/skelsec/minidump
- Packaged version: `0.0.24`
- License: MIT
- Relationship: bundled Python dependency used by the private Werseter source host
- Modifications: none

The dependency is bundled so supported source-ZIP workflows do not require a separate Python installation or a first-run `pip` operation. Its original license and authorship remain in force. The full license is shipped as `third_party/licenses/minidump-0.0.24.txt` in source and inside finished packages.

## Blue Star Manager research

Product and workflow research compared Uma Mod Manager with Blue Star Manager. Ideas were independently reimplemented behind Uma Mod Manager's own immutable-library and transactional-deployment architecture. No Blue Star Manager source is bundled unless separately documented and permitted by its license.

See [`docs/MANAGER_BSTAR_REVIEW.md`](docs/MANAGER_BSTAR_REVIEW.md).

## Runtime dependencies

Packaged builds include or depend on open-source libraries such as UnityPy, Pillow, PyYAML, vdf, certifi, APSW builds, minidump, PyInstaller, CPython, and their transitive dependencies. Their notices and licenses remain those of the respective upstream projects and packaged distributions.

Before adding a bundled dependency or external tool, contributors must record:

- project and author;
- source repository;
- exact version or revision;
- license;
- whether it is linked, imported, executed externally, or redistributed;
- modifications made by this project;
- any required notices or source-distribution obligations.

## Game and third-party assets

Uma Musume Pretty Derby and its assets belong to their respective rights holders. Uma Mod Manager is not affiliated with Cygames.

Mods remain the work of their creators. The Manager must preserve mod authorship, version, source, and redistribution terms when known. Do not place copyrighted game assets, decrypted databases, or third-party mod files in this repository without permission.

## Reporting an omission

Open an issue when a credit, license, or provenance entry is missing or inaccurate. Include the project URL, relevant file or feature, and the correction requested. Licensing mistakes are bugs, even when the UI looks particularly charming around them.

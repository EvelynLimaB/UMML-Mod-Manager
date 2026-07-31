# Branding and compatibility identifiers

## Public identity

The project and repository are named **Uma Mod Manager**.

Repository:

```text
https://github.com/EvelynLimaB/Uma-Mod-Manager
```

The project is a fork and continuation of **UMML / UmaMusume Mod Loader**. The new name makes the purpose understandable to people who have never encountered the original acronym, while the original name remains part of the project's technical and historical lineage.

## Why technical identifiers still say `umml`

Renaming an application is easy. Renaming every package, command, desktop ID, Python module, data directory, recovery path, and automation contract without duplicating or abandoning user state is not.

During the compatibility window, these identifiers remain stable:

| Purpose | Stable identifier |
| --- | --- |
| Debian package | `umml-manager` |
| GUI command | `umml-manager` |
| CLI command | `umml-manager-cli` |
| Python package | `umml_manager` |
| AppStream/desktop ID | `io.github.evelynlimab.ummlmanager` |
| Linux application payload | `/usr/lib/umml-manager` |
| Linux data root | `~/.local/share/umml-manager` |
| Windows data root | `%LOCALAPPDATA%\UMML Manager` |
| Existing CI artifact family | `umml-manager-*` |

These are compatibility contracts, not unfinished branding.

Changing them casually would risk:

- installing a second package instead of upgrading the first;
- creating a new empty data root while the real library and baselines remain elsewhere;
- losing desktop launcher upgrades;
- breaking user scripts and automation;
- fragmenting recovery journals and target-bound baselines;
- making old and new builds disagree about who owns deployed state.

## User-visible naming

New user-facing surfaces should say **Uma Mod Manager**, including:

- repository documentation;
- application window title;
- desktop launcher name;
- AppStream catalogue name;
- workflow display names;
- portable archive readme and primary launcher;
- issue templates and project descriptions.

Where useful, documentation may say:

```text
Uma Mod Manager (formerly UMML-Manager)
```

Do not rename the original upstream project. Historical references should use **UMML / UmaMusume Mod Loader** and link to the original repository.

## Windows portable transition

The primary launcher is:

```text
Uma Mod Manager.cmd
```

A compatibility launcher may remain:

```text
UMML Manager.cmd
```

Both launch the same packaged executable and use the same data root.

## Future identifier migration

A future stable release may introduce new technical identifiers only through an explicit migration plan that includes:

1. detection of every previous data root;
2. atomic state migration with backups and verification;
3. package replacement or transitional dependency metadata;
4. desktop-ID and launcher compatibility aliases;
5. rollback instructions;
6. clean-install and upgrade tests on Windows, Debian-family systems, and AppImage;
7. proof that baselines, profiles, transactions, workspaces, and external-tool settings survive unchanged.

Until those gates exist, retaining `umml` identifiers is safer and more professional than performing a cosmetic rename that quietly abandons people's state.

## Naming in code

New domain classes and modules do not need an additional `UMML` prefix. Use names that describe their function. Existing public imports and compatibility modules should not be renamed without a deprecation and migration path.

The original `UMML.py`, `UMML_core.py`, and related paths are compatibility code. They should remain clearly identified as upstream-derived behavior rather than being presented as newly authored Manager components.

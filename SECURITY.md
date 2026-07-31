# Security policy

UMML-Manager imports untrusted mod packages, reads game metadata, launches optional external tools, and can modify local game asset files. Security reports should be handled with more care than an ordinary UI bug whose greatest victim is a misaligned button.

## Supported versions

Security fixes currently target the active UMML-Manager preview branch and the newest published Manager build. The preserved legacy UMML compatibility release is maintained only for severe issues affecting shared discovery, packaging, or destructive file behavior.

| Product | Version | Security support |
| --- | --- | --- |
| UMML-Manager | Current alpha preview | Yes |
| UMML-Manager | Older preview artifacts | Upgrade first; fixes are not backported routinely |
| Legacy UMML compatibility layer | `1.5.0-linux.6` | Severe shared/destructive issues only |

## Reporting a vulnerability

Prefer GitHub private vulnerability reporting when it is enabled for the repository. Otherwise contact the repository owner privately through GitHub before publishing technical details.

Include only the minimum necessary information:

- affected version or commit;
- operating system and package format;
- affected provider, archive, external tool, or state format;
- reproducible steps using synthetic data where possible;
- expected and actual behavior;
- impact;
- whether game files, Manager state, or personal data were exposed or modified.

Do not attach copyrighted game assets, decrypted databases, real mod archives without permission, personal roster data, access tokens, cookies, Steam credentials, Wine prefixes, recovery snapshots, or full logs containing private paths.

## High-priority report categories

Please report privately before disclosure when an issue can:

- escape archive or workspace path containment;
- write outside the selected game target;
- replace verified vanilla baselines with modded data;
- bypass closed-game mutation checks;
- execute archive or provider content;
- invoke a shell with untrusted values;
- load arbitrary native code through an ordinary mod package;
- corrupt or discard recovery journals, baselines, or active state silently;
- overwrite externally changed files without warning;
- expose account identifiers or personal roster data;
- let an external tool inherit deployment privileges unexpectedly;
- bypass provider certificate verification;
- confuse one installation's active state or baselines with another target;
- allow a malformed package to mutate immutable imported source.

## Archive and provider threat model

All downloaded and local packages are untrusted, even when obtained over HTTPS.

Supported import paths must validate before extraction or copying:

- parent traversal;
- absolute and drive-letter paths;
- symbolic and hard links;
- devices, FIFOs, sockets, and special files;
- duplicate output paths;
- excessive names, entries, or expanded size;
- encrypted entries that cannot be inspected safely;
- executable installer content;
- output escaping the staging directory.

Providers may browse, download, and import. They must not deploy files or receive the live game `dat` path.

## Deployment safety

Apply and restore require:

- a verified installation target;
- a closed-game process check;
- a complete resolver plan;
- verified prepared payloads;
- target-bound vanilla baselines;
- a durable transaction journal;
- staging and post-write verification;
- rollback or recovery evidence.

Unknown or corrupt critical state must fail closed. Preference corruption may be quarantined and reset with the original bytes preserved; deployment evidence may not be silently discarded.

## External tools and process-memory utilities

UMML-Manager may launch user-selected external tools in separate processes and import their output. It does not grant those tools access to Manager deployment, baselines, profiles, or recovery state.

The Manager must not run as administrator or root merely because an external memory reader requests elevated access. Run such tools separately and import their bounded output.

External code or binaries are not bundled without a compatible license or explicit permission. Credits do not substitute for permission.

## Personal and roster data

Veteran-roster imports are treated as untrusted personal data.

The Manager removes known viewer/account identifiers and account-name fields before storing immutable snapshots. Reports involving missed identifiers should provide a redacted synthetic example or only the affected field names and structure.

Never publish a real roster dump in an issue.

## Safe testing

Security and recovery tests should use:

- temporary Manager roots;
- synthetic game trees;
- generated archives;
- disposable package fixtures;
- copied metadata or target structures only when redistribution is legal;
- no automatic discovery of a real installation.

Do not test destructive behavior against a live personal game installation merely because the code includes rollback. That is evidence of courage, not methodology.

## Disclosure

Please allow reasonable time for validation, a fix, package rebuilding, and coordinated disclosure. Public credit is welcome when requested, subject to the reporter's preference and the absence of private or copyrighted material.

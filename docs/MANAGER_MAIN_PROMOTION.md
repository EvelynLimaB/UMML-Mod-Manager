# UMML Manager main-promotion policy

This document defines the evidence required before the Manager preview branch can become `main`. It does not declare a stable release merely because CI is green. Computers remain talented at passing synthetic tests before meeting one particular desktop and developing a personality disorder.

## Exact revision rule

Promotion evidence belongs to one exact branch head. Any code, workflow, version, packaging, or documentation change after validation requires new artifacts and new evidence.

Record:

- exact commit SHA;
- Python checks run;
- Linux Manager checks run;
- Windows Manager checks run when Windows is advertised;
- artifact IDs and expiration dates;
- external SHA-256 values;
- real-machine results tied to those exact downloads.

## Automated gates

The exact head must pass:

1. Python syntax and project checks.
2. Manager structural, architecture, dangerous-call, and visible-button audits.
3. Full Manager regression suite on Linux and Windows.
4. End-to-end configurable package preparation, profile switching, deployment, vanilla restoration, and immutable-source verification.
5. Source GUI rendering for every page in Light and Dark modes.
6. Frozen runtime self-test and GUI smoke tests.
7. DEB and AppImage construction, inspection, installation lifecycle, runtime parity, and checksums.
8. Native Windows PyInstaller construction, packaged self-test, dual-theme GUI smoke, portable ZIP assembly, and checksum artifact.
9. Installation detection, provider, TLS, profile verification, recovery, and disposable deployment gates already required by the Manager workflows.

## Configurable package gates

The release candidate must prove that:

- package targets, tags, regions, dependencies, incompatibilities, and relative load order survive import and registry reload;
- invalid or contradictory policy leaves no immutable source or partial registry record;
- **Edit package** works for modern and legacy manifest-less imports through workspace copies;
- Save changes only the workspace;
- Save-and-import requires a new immutable ID/version for edited bytes;
- one imported package may contain multiple authored character or dress variants;
- two variants may safely map to the same game target because each prepared payload has an isolated source root;
- profile selection changes the resolved payload and conflict plan without mutating imported source files;
- switching profile variants transactionally replaces the target and an empty profile restores vanilla;
- stale configurable caches require re-preparation rather than guessing.

Target metadata remains descriptive. Arbitrary Unity bundle retargeting is excluded until a generated-transform backend has exact metadata/game-build validation and restoration tests.

## Real-machine gates

### Windows

On the exact portable Windows artifact:

1. Extract into a fresh ordinary user-owned directory.
2. Launch `UMML Manager.cmd` without a development Python environment.
3. Confirm Steam Global/Japan or the intended Windows installation is detected correctly.
4. Confirm Manager data uses `%LOCALAPPDATA%\UMML Manager`, or preserves a detected early preview root without appearing empty.
5. Test Light/System/Dark switching and restart persistence.
6. Test **Open workspaces** and **Open manager data** through Explorer.
7. Create a package with affected characters, dresses, content types, compatibility rules, and a character selector.
8. Save/import it as a new version, prepare it, choose different variants in two profiles, and inspect the changed conflict plan.
9. On disposable game data, apply one variant, switch to the other, disable it, and restore exact originals.
10. Verify imported source bytes remain unchanged.
11. Exercise diagnostics and a clean restart.

### Bazzite/Linux

On the exact AppImage:

1. `scripts/manager_main_gate.sh` returns `RESULT: PASS`.
2. Folder-opening buttons work on the live desktop.
3. Light/System/Dark and every page render correctly.
4. The same package creation, edit, configuration, conflict, variant-switch, and restore flow passes.

### Mint/Debian

On the exact DEB:

1. Upgrade/install succeeds and launches `/usr/bin/umml-manager`.
2. Detection, folder opening, themes, package editing, configuration, conflict planning, and restart persistence work.
3. User data survives package removal or upgrade.

## Stable-release gates not implied by main promotion

- broader current real-mod corpus;
- destructive process-kill recovery drills at every transaction phase;
- game-update metadata and baseline rebase workflow;
- native Hachimi deployment;
- generated arbitrary character/dress retargeting;
- provider-neutral version/update centre and rollback UI;
- one-click `umml:` protocol;
- native Studio parity replacing the guarded compatibility host;
- signed release and update metadata.

Keep the PR draft until exact artifacts pass the applicable real-machine gates. Do not reinterpret a successful Linux package as Windows evidence, or a successful Windows portable build as proof that one user's Steam layout has stopped being inventive.

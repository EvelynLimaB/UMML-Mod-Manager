# Uma Mod Manager main-promotion policy

This document defines the evidence required before a Manager development branch can become `main`. It does not declare a stable Manager release merely because CI is green, a Community Test exists, or a desktop opened once without visible smoke.

Use [RELEASE_PROCESS.md](RELEASE_PROCESS.md) for Community Test publication and [MANAGER_RELEASE_CHECKLIST.md](MANAGER_RELEASE_CHECKLIST.md) for stable-release gates.

## Exact revision rule

Promotion evidence belongs to one exact branch head. Any code, workflow, version, packaging, or documentation change after validation requires new artifacts and new evidence.

Record:

- exact commit SHA;
- Legacy compatibility, Linux Manager, and Windows Manager workflow runs;
- manual testing-release workflow when relevant;
- artifact IDs and expiration dates;
- external SHA-256 values;
- real-machine results tied to those exact downloads;
- unresolved safety, compatibility, UX, and documentation findings.

## Automated gates

The exact head must pass:

1. Python syntax and project checks.
2. Manager structural, architecture, dangerous-call, and visible-button audits.
3. Branding/compatibility and exact release-contract audits.
4. Full Manager regression suite on Linux and Windows.
5. End-to-end configurable package preparation, profile switching, deployment, vanilla restoration, and immutable-source verification.
6. Source GUI rendering for every page in Light and Dark modes.
7. Frozen runtime self-test and GUI smoke tests.
8. DEB and AppImage construction, inspection, installation lifecycle, runtime parity, and checksums.
9. Native Windows PyInstaller construction, packaged self-test, dual-theme GUI smoke, portable ZIP assembly, and checksums.
10. Installation detection, provider, TLS, profile verification, recovery, and disposable deployment gates required by Manager workflows.
11. Support-bundle privacy, symlink, bounded-output, and finished-package documentation checks.

## Configurable package gates

The candidate must prove that:

- package targets, tags, regions, dependencies, incompatibilities, and relative load order survive import and registry reload;
- invalid or contradictory policy leaves no immutable source or partial registry record;
- **Inspect & edit** works for modern and legacy manifest-less imports through workspace copies;
- saving changes only the workspace until explicit validated import;
- save-and-import requires a new immutable ID/version for edited bytes;
- one imported package may contain multiple authored character or dress variants;
- two variants may safely map to the same game target because each prepared payload has an isolated source root;
- profile selection changes the resolved payload and conflict plan without mutating imported source files;
- switching profile variants transactionally replaces the target and an empty profile restores vanilla;
- stale metadata and older cache formats are queued for automatic maintenance rather than asking users to prepare or re-prepare by hand;
- a failed package preserves source and prior verified cache while the remaining automatic queue continues.

Target metadata remains descriptive. Arbitrary Unity bundle retargeting is excluded until a generated-transform backend has exact metadata/game-build validation and restoration tests.

## Testing and feedback gates

Before a testing-focused branch is promoted:

- exact release notes and tester guidance exist;
- the Testing feedback issue form accepts pass, partial, and failure reports;
- Settings can generate a privacy-scrubbed support bundle;
- packaged documentation explains inspection and privacy boundaries;
- published-artifact replacement is refused under an existing tag;
- rollback keeps the previous application package and preserves external Manager state;
- Community Test limitations are explicit and do not imply stable support.

## Real-machine gates

### Windows

On the exact Windows portable artifact:

1. Extract into a fresh ordinary user-owned directory.
2. Launch `Uma Mod Manager.cmd` without a development Python environment.
3. Confirm Steam Global/Japan or the intended Windows installation is detected correctly.
4. Confirm Manager data uses `%LOCALAPPDATA%\UMML Manager`, or preserves a detected early preview root without appearing empty.
5. Test Light/System/Dark switching and restart persistence.
6. Test **Open workspaces** and **Open manager data** through Explorer.
7. Create a package with affected characters, dresses, content types, compatibility rules, and a character selector.
8. Save/import it as a new version, allow automatic preparation, choose different variants in two profiles, and inspect the changed conflict plan.
9. On disposable or independently backed-up game data, apply one variant, switch to the other, disable it, and restore exact originals.
10. Verify imported source bytes remain unchanged.
11. Exercise diagnostics, **Create support bundle**, manual report inspection, and a clean restart.
12. Keep the previous portable folder and confirm application rollback still sees the same Manager data.

### Bazzite/Linux

On the exact AppImage:

1. `scripts/manager_main_gate.sh` returns `RESULT: PASS`.
2. Folder-opening buttons work on the live desktop.
3. Light/System/Dark and every page render correctly.
4. The same package creation, inspection, configuration, conflict, variant-switch, and restore flow passes.
5. Support-bundle creation and manual privacy inspection pass.
6. The previous AppImage remains a working application rollback.

### Mint/Debian

On the exact DEB:

1. Upgrade/install succeeds and launches `/usr/bin/umml-manager`.
2. Detection, folder opening, themes, package inspection/editing, configuration, conflict planning, and restart persistence work.
3. User data survives package removal, upgrade, and reinstall of the previous package.
4. Support-bundle creation works from the installed package.
5. Original UMML compatibility packages remain unaffected.

## Stable-release gates not implied by main promotion

- broader current real-mod corpus;
- destructive process-kill recovery drills at every transaction phase;
- game-update metadata and baseline rebase workflow;
- native Hachimi deployment;
- generated arbitrary character/dress retargeting;
- provider-neutral version/update centre and rollback UI;
- one-click `umml:` protocol;
- native Studio parity replacing the guarded compatibility host;
- signed release artifacts and authenticated update metadata;
- broader privacy review of support reports against real-world diagnostics.

UM:PD Dark Mode remains outside ordinary package support because it is a self-installing executable patch. It requires a separately trusted, exact-base patch backend and is never executed through normal mod import.

Keep the PR draft until exact artifacts pass the applicable real-machine gates. Do not reinterpret a Linux package as Windows evidence, a successful package build as proof of a live provider, or three quiet days as a statistically meaningful test campaign. Computers and humans are both fully capable of failing silently for unrelated reasons.

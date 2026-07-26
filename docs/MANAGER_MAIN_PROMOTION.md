# UMML Manager main-promotion gate

This gate decides whether PR #2 can merge the UMML Manager alpha preview into `main`. It does not rename the Manager stable, publish a stable Manager release, or waive the broader [release checklist](MANAGER_RELEASE_CHECKLIST.md).

Evidence is revision-specific. Every automated result and Bazzite report must identify the exact PR head commit and alpha14 artifact. Results from an older artifact do not promote a newer commit.

## Required repository and CI evidence

- The PR head is mergeable into current `main`, contains no unresolved review thread, and passes `git diff --check`.
- `bash scripts/check_all.sh` passes from a clean checkout.
- Manager and legacy workflows pass for the exact head commit.
- The Manager workflow is configured for Manager changes pushed to `main`.
- Source installation upgrades an isolated historical alpha1 layout, launches the current CLI self-test, uninstalls cleanly, and preserves library/deployment sentinels.
- One frozen runtime produces the DEB and AppImage, and their complete runtime trees match.
- Source, frozen, extracted DEB, installed DEB, and AppImage entry points pass the same disposable deployment/recovery self-test.
- Every native Tk page constructs and renders under Xvfb from source and each finished package layout.
- The real Debian package installs and removes in CI without deleting Manager user data.
- Package names, versions, metadata, embedded CA data, Pillow runtime, and external SHA-256 checksums validate.

## Required Bazzite evidence

Use the AppImage artifact built by the exact passing workflow. Close Umamusume, verify `SHA256SUMS`, and run from the repository checkout:

```bash
scripts/manager_main_gate.sh \
  --appimage /path/to/umml-manager_0.2.0-alpha14_x86_64.AppImage \
  --checksums /path/to/SHA256SUMS \
  --profile Default \
  --output ./umml-manager-main-gate.log
```

`RESULT: PASS` proves all of the following on that machine:

- the exact AppImage starts and reports its expected version;
- disposable import, profile conflict, apply/switch/restore, external-change refusal, legacy-baseline migration, and interrupted recovery succeed;
- platform, HTTPS trust, saved installation, metadata fingerprint, profile registries, process inspection, pending transactions, active state, and vanilla baseline scope are ready;
- current GameBanana browse/detail/file metadata and preview decoding work without disabling TLS verification;
- Library, Discover, Studio, Conflicts, and Settings construct and render through native Tk;
- the real `Default` profile resolves with its prepared payloads and installation identity;
- its winners, conflicts, current active state, and legacy originals can apply and restore on disposable copies;
- the real game targets are hash-checked before and after and remain unchanged.

The log can contain local paths. Sanitize it before attaching it to the PR. Record only truthful results; a skipped profile check is an incomplete gate.

## Explicit alpha-preview exclusions

These are not blockers for merging the alpha preview into `main`, but they remain blockers for the corresponding stable claim:

- UM:PD Dark Mode is a self-installing executable patch. The Manager neither runs it nor claims generic import support for it.
- Pure Hachimi packages remain non-deployable until a separately tested backend exists.
- 7z/RAR support, native Windows packaging, an in-game injector, hot reload, multi-installation convenience UI, and automatic dependency installation are not advertised as complete.
- Live destructive profile deployment, controlled process-kill recovery, game-update baseline rebasing, broad current-mod corpus testing, and second-distribution coverage remain on the stable release checklist.

## Promotion sequence

1. Push the candidate and wait for exact-head workflows.
2. Run the Bazzite gate against that workflow's AppImage and checksum artifact.
3. Attach the sanitized PASS evidence to PR #2.
4. Resolve any remaining review threads, convert the PR from draft, and merge without rewriting the tested head.
5. Confirm Manager and legacy workflows pass on the resulting `main` commit.

If step 5 fails, treat `main` as unhealthy and fix it immediately; do not publish a Manager release from that commit.

# Umadump and UmaExtractor veteran-roster integration

Uma Mod Manager can import and analyse compatible veteran-roster JSON produced by
several related community tools:

- [rockisch/umadump](https://github.com/rockisch/umadump), the original public
  project and classic `data.json` format;
- [NECOtype/UmaExtractor](https://github.com/NECOtype/UmaExtractor) and the
  related xancia update, which retain the classic roster-oriented workflow;
- [Werseter/umadump](https://github.com/Werseter/umadump), the newer 2.0 runtime
  reader whose veteran output is `trained_chara_data.json`.

The tools are not interchangeable internally. The Manager integrates their
output at a validated JSON boundary rather than treating one scanner
implementation as its own code.

## Normal player workflow

The Veteran Roster window accepts three kinds of external-tool input through
**Install or choose extractor**:

1. an upstream standalone executable;
2. an individual Python entry-point script;
3. a downloaded source ZIP from a recognized provider.

For a recognized Werseter source ZIP, the user selects the ZIP itself. The
Manager then:

1. verifies that the input is a regular ZIP file;
2. rejects traversal paths, absolute paths, links, special files, encrypted
   members, duplicate case-insensitive paths, excessive entry counts, and
   excessive compressed or expanded sizes;
3. requires exactly one project root containing the expected Werseter files;
4. calculates the archive SHA-256 and detects the upstream version;
5. extracts the source into a hash-addressed Manager-owned tools directory;
6. preserves that installed source as an immutable provider version;
7. locates Python 3.14 or newer when available;
8. creates a private virtual environment for that extractor version;
9. installs only the dependencies declared by the upstream
   `requirements.txt`;
10. launches the extractor as a separate process with update checks disabled;
11. directs output to the isolated Veteran inbox;
12. imports the latest valid roster automatically after a successful run.

If Python 3.14 is unavailable, the safe source installation still completes and
the UI explains that the user must install a compatible interpreter or select an
upstream standalone executable. The Manager never substitutes its frozen Python
runtime, because that executable is the Manager itself rather than a general
Python interpreter.

The installed source and runtime live below the private Veteran data root:

```text
tools/
└── werseter-umadump/
    └── <version>-<archive-sha-prefix>/
        ├── managed-extractor.json
        ├── source/
        └── runtime/        # only when Python 3.14+ was available
```

Selecting the same source ZIP again is idempotent. A different archive hash is a
new managed provider version instead of an in-place rewrite.

## What the provider families do

### Original umadump lineage

The original `rockisch/umadump` attaches with Frida, locates a cached MsgPack
response containing `trained_chara_array`, and writes `data.json`. Updated
UmaExtractor forks use more resilient scans while preserving a compatible
roster-oriented result.

A classic `data.json` does not identify which compatible implementation created
it. The Manager therefore records the provider as **umadump-compatible
extractor** and adds a provenance warning rather than inventing certainty from a
filename.

### Werseter umadump 2.0

Werseter's rewrite reads live IL2CPP objects or a full-memory minidump, validates
wrapper layouts against `global-metadata.dat`, and writes several independent
outputs. The veteran roster is `trained_chara_data.json`; other files include
support cards, owned cards, friends, trophies, race replays, and idle single-mode
state.

The Manager accepts `trained_chara_data.json` as a veteran snapshot. It rejects
those other output classes as rosters. When **Import latest output** selects
another Werseter JSON from the same folder, the importer may use the validated
sibling `trained_chara_data.json` and records a warning explaining the
substitution.

## Attribution and licensing boundary

None of the referenced repository roots currently declares a project-wide
software license. Uma Mod Manager therefore does **not** copy, modify, vendor,
build, or redistribute their source or binaries in its own release packages.

Managed ZIP installation does not change that boundary:

- the user independently downloads the upstream archive;
- the Manager installs the user's selected bytes locally;
- the archive SHA-256, provider, version, paths, and runtime status are recorded;
- the tool remains a separate process;
- no upstream source enters the Manager process or repository;
- no upstream binary or source archive is republished by Uma Mod Manager;
- UI and documentation retain the original project links and credits.

Bundling or adapting implementation code requires an explicit license or written
permission from the relevant copyright holders. Attribution is required, but it
is not permission wearing a polite hat.

## Privacy and provenance

Imported JSON is treated as untrusted personal data. Before a snapshot is
stored, the Manager:

1. rejects links, special files, oversized inputs, malformed JSON, non-object
   roster entries, and arrays that do not resemble trained-character data;
2. removes snake_case and camelCase viewer IDs recursively;
3. removes known trainer and circle-name fields such as `user_name` and
   `circle_name` recursively;
4. retains the actual source-file SHA-256 for provenance without retaining those
   private fields;
5. stores an immutable, timestamped snapshot under the Manager data root;
6. records the inferred provider, source filename, import time, format, warnings,
   and undeclared-license status;
7. treats an identical source hash as an idempotent re-import.

The snapshot browser shows raw scrubbed records because community extractor
formats can gain fields before the Manager has a named presentation for them.
Unknown fields are preserved rather than silently discarded.

## Compatibility currently implemented

The Studio page exposes **Veteran roster**, which provides:

- managed installation of recognized Werseter source ZIPs;
- optional selection of an external executable or Python script;
- private per-version Python environments when Python 3.14+ is available;
- shell-free external process launching;
- automatic import after successful extraction;
- manual import of classic `data.json`, Werseter `trained_chara_data.json`, and
  compatible wrapped arrays;
- an isolated external-extractor inbox and log;
- immutable local snapshots;
- recursive privacy-field removal;
- provider and format detection;
- rejection of support-card, owned-card, friend, trophy, and replay arrays as
  veteran rosters;
- search and sortable veteran tables;
- snake_case and camelCase ID/stat/factor/skill handling;
- stats, skills, factors, aptitude, and trained-character ID inspection;
- raw scrubbed-record inspection;
- filtered CSV export;
- complete snapshot export with provenance;
- visible upstream credits and licensing status.

## Safety boundary

Veteran-roster tools are read-only from Uma Mod Manager's perspective. They do
not receive access to mod deployment, vanilla baselines, recovery journals,
profiles, or the `Persistent/dat` write path.

The external extractor may need the game running because it reads process
memory. This does not relax the deployment policy: applying or restoring mods
remains blocked while the game is running.

The Manager itself never requests administrator or root access for extraction.
Linux providers may use `/proc`, `process_vm_readv`, Frida, or another mechanism
with different host permission requirements. The user runs any elevated
provider separately and imports the resulting JSON; the Manager GUI must not be
elevated.

Installing dependencies from a user-selected source package can execute ordinary
Python packaging hooks. It therefore runs only inside the extractor's private
environment, never as root, and only after explicit confirmation. The archive is
validated before extraction, but the upstream source remains third-party code.

## Deliberately deferred

The current stage does not claim to:

- identify every borrowed or transient record returned by game memory;
- resolve every numeric ID to a localized name through `master.mdb`;
- calculate inheritance probabilities or compatibility scores;
- browse Werseter's support-card, card, friend, trophy, replay, or training-state
  outputs in dedicated pages;
- bundle any extractor;
- download upstream source automatically without a declared redistribution
  boundary;
- install Python 3.14 system-wide;
- automate Linux privilege escalation;
- hook IL2CPP or scan game memory from the Manager itself.

Those features require versioned schemas, real output samples, master-database
resolution, explicit upstream licensing, and a separate safety review. A polished
table is still not evidence that memory-derived data is infallible, however much
software enjoys putting uncertainty in a cardigan.

# Umadump and UmaExtractor veteran-roster integration

UMML Manager can import and analyse compatible veteran-roster JSON produced by
several related community tools:

- [rockisch/umadump](https://github.com/rockisch/umadump), the original public
  project and classic `data.json` format;
- [NECOtype/UmaExtractor](https://github.com/NECOtype/UmaExtractor) and the
  related xancia update, which retain the classic roster-oriented workflow;
- [Werseter/umadump](https://github.com/Werseter/umadump), the newer 2.0 runtime
  reader whose veteran output is `trained_chara_data.json`.

The tools are not interchangeable internally. UMML integrates their output at a
validated JSON boundary rather than treating one scanner implementation as the
Manager's own code.

## What the provider families do

### Original umadump lineage

The original `rockisch/umadump` attaches with Frida, locates a cached MsgPack
response containing `trained_chara_array`, and writes `data.json`. Updated
UmaExtractor forks use more resilient scans while preserving a compatible
roster-oriented result.

A classic `data.json` does not identify which compatible implementation created
it. UMML therefore records the provider as **umadump-compatible extractor** and
adds a provenance warning rather than inventing certainty from a filename.

### Werseter umadump 2.0

Werseter's rewrite reads live IL2CPP objects or a full-memory minidump, validates
wrapper layouts against `global-metadata.dat`, and writes several independent
outputs. The veteran roster is `trained_chara_data.json`; other files include
support cards, owned cards, friends, trophies, race replays, and idle single-mode
state.

UMML accepts `trained_chara_data.json` as a veteran snapshot. It rejects those
other output classes as rosters. When the historical **Import latest output**
action selects another Werseter JSON from the same folder, the importer may use
the validated sibling `trained_chara_data.json` and records a warning explaining
the substitution.

## Attribution and licensing boundary

None of the referenced repository roots currently declares a project-wide
software license. UMML therefore does **not** copy, modify, vendor, build, or
redistribute their source or binaries.

The Manager integration is an external-tool adapter only:

- the user selects their own upstream executable or script;
- UMML launches it as a separate process without `shell=True`;
- output may be directed to an isolated Manager-owned inbox when the external
  tool respects its current working directory;
- the user may run any provider independently and import `data.json` or
  `trained_chara_data.json` manually;
- the UI and documentation credit the original project, maintained forks,
  rewrites, and contributors;
- no upstream scanner code is included in UMML packages.

Bundling or adapting implementation code requires an explicit license or written
permission from the relevant copyright holders. Attribution is required, but it
is not permission wearing a polite hat.

## Privacy and provenance

Imported JSON is treated as untrusted personal data. Before a snapshot is
stored, UMML:

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
formats can gain fields before UMML has a named presentation for them. Unknown
fields are preserved rather than silently discarded.

## Compatibility currently implemented

The Studio page exposes **Veteran roster**, which provides:

- manual import of classic `data.json`, Werseter `trained_chara_data.json`, and
  compatible wrapped arrays;
- an isolated external-extractor inbox;
- optional selection and launching of an external executable or Python script;
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

Veteran-roster tools are read-only from UMML's perspective. They do not receive
access to mod deployment, vanilla baselines, recovery journals, profiles, or the
`Persistent/dat` write path.

The external extractor may need the game running because it reads process
memory. This does not relax UMML's deployment policy: applying or restoring mods
remains blocked while the game is running.

UMML itself never requests administrator or root access for extraction. Linux
providers may use `/proc`, `process_vm_readv`, Frida, or another mechanism with
different host permission requirements. The user runs any elevated provider
separately and imports the resulting JSON; the Manager GUI must not be elevated.

## Deliberately deferred

The current stage does not claim to:

- identify every borrowed or transient record returned by game memory;
- resolve every numeric ID to a localized name through `master.mdb`;
- calculate inheritance probabilities or compatibility scores;
- browse Werseter's support-card, card, friend, trophy, replay, or training-state
  outputs in dedicated pages;
- bundle any extractor;
- automate Linux privilege escalation;
- hook IL2CPP or scan game memory from UMML itself.

Those features require versioned schemas, real output samples, master-database
resolution, explicit upstream licensing, and a separate safety review. A polished
table is still not evidence that memory-derived data is infallible, however much
software enjoys putting uncertainty in a cardigan.

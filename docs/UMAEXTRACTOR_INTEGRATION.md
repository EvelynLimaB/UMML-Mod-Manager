# UmaExtractor veteran-roster integration

UMML Manager can import and analyse `data.json` files produced by the external
[NECOtype/UmaExtractor](https://github.com/NECOtype/UmaExtractor) project.

## Attribution and licensing boundary

The referenced repository describes itself as an updated fork of `umadump` and
credits the original project and community contributors. Its current tree does
not declare a project-wide software license. UMML therefore does **not** copy,
modify, vendor, build, or redistribute UmaExtractor source or binaries.

The Manager integration is an external-tool adapter only:

- the user selects their own upstream executable or script;
- UMML launches it as a separate process without `shell=True`;
- output is directed to an isolated Manager-owned inbox when the external tool
  respects its current working directory;
- the user may also run the tool independently and import `data.json` manually;
- the UI links to and credits the upstream project, the updated `xancia` fork,
  the original `umadump` work, and their contributors;
- no upstream code is included in UMML packages.

Bundling or adapting upstream implementation code requires an explicit license
or written permission from the relevant copyright holders. Attribution is not a
substitute for permission.

## Privacy and provenance

Imported JSON is treated as untrusted personal data. Before a snapshot is
stored, UMML:

1. rejects links, special files, oversized inputs, malformed JSON, and
   non-object roster entries;
2. removes `viewer_id` and `owner_viewer_id` recursively;
3. retains the original file SHA-256 for provenance without retaining those
   private fields;
4. stores an immutable, timestamped snapshot under the Manager data root;
5. records the external provider, source filename, import time, warnings, and
   undeclared-license status;
6. treats an identical source hash as an idempotent re-import.

The snapshot browser shows raw scrubbed records because community extractor
formats may gain fields before UMML has a named presentation for them. Unknown
fields are preserved rather than silently discarded.

## Safety boundary

Veteran-roster tools are read-only from UMML's perspective. They do not receive
access to mod deployment, vanilla baselines, recovery journals, profiles, or the
`Persistent/dat` write path.

The external extractor may need the game running because it reads process
memory. This does not relax UMML's deployment policy: applying or restoring mods
remains blocked while the game is running.

UMML itself never requests administrator or root access for extraction. On
Linux, if an upstream script requires `/proc/<pid>/mem` privileges, the user must
run that tool separately and import the resulting JSON. The Manager GUI must not
be elevated.

## Implemented first stage

The Studio page exposes **Veteran roster**, which provides:

- manual `data.json` import;
- an isolated external-extractor inbox;
- optional selection and launching of an external executable or Python script;
- immutable local snapshots;
- recursive privacy-field removal;
- search and sortable veteran tables;
- stats, skills, factor and aptitude inspection;
- raw scrubbed-record inspection;
- filtered CSV export;
- complete snapshot export with provenance;
- visible upstream credits and licensing status.

## Deliberately deferred

The first stage does not claim to:

- identify every borrowed or transient record returned by game memory;
- resolve every numeric ID to a localized name;
- calculate inheritance probabilities or compatibility scores;
- bundle the extractor;
- automate Linux privilege escalation;
- hook IL2CPP or scan game memory from UMML itself.

Those features require a versioned schema, a broader real-roster corpus,
master-database resolution, explicit upstream licensing, and separate safety
review. A polished table is not evidence that memory-derived data is infallible,
however much software enjoys dressing uncertainty in neat columns.

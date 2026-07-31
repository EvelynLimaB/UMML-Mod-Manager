# Uma Mod Manager project vision

## Mission

Uma Mod Manager exists to make **using mods safer** and **making mods easier** for Umamusume Pretty Derby.

The project succeeds when:

- a normal player can discover, install, configure, switch, update, and remove mods without understanding game hashes or internal preparation stages;
- a new creator can inspect a working mod, understand what it affects, make a variant, test it safely, and publish a well-described package;
- experienced creators can automate advanced workflows without abandoning provenance, validation, recovery, or compatibility metadata;
- community tools remain credited and interoperable instead of being copied into one opaque application;
- more people publish maintainable mods because the boring technical work has been removed from their path.

## Product identity

Uma Mod Manager is a fork and continuation of [UMML / UmaMusume Mod Loader](https://github.com/tumugu/UmaMusume_Mod_Loader). The original project proved that Umamusume asset replacement and editing workflows could be made practical. This repository takes the next step: one cross-platform application centered on a real mod library, profiles, package metadata, creator workspaces, and safe deployment.

The original UMML code remains a compatibility layer and source of proven domain behavior. It is not discarded merely to make the tree look fashionable. New work should move toward tested headless services and native Manager pages rather than adding more tightly coupled popup logic.

The public product name is **Uma Mod Manager**. Technical `umml-manager` identifiers remain stable until an explicit state and package migration is tested. See [`BRANDING_AND_COMPATIBILITY.md`](BRANDING_AND_COMPATIBILITY.md).

## Primary audiences

### Players

Players should be able to:

- find mods;
- understand what they affect;
- install them safely;
- select variants;
- build named profiles;
- preview conflicts;
- apply a setup;
- switch setups;
- return to vanilla;
- recover from interruption or an incompatible update.

They should not need to:

- prepare or re-prepare packages manually;
- rename files to enable options;
- copy hashes into game folders;
- guess which mod won a conflict;
- maintain separate backup rituals for every package;
- edit JSON for ordinary configuration;
- run the Manager as administrator or root.

### Mod creators

Creators should be able to:

- inspect source bundles and final targets;
- identify likely characters, dresses, models, textures, audio, effects, UI, and parts;
- correct or enrich detected metadata;
- define dependencies, incompatibilities, regions, and relative load order;
- create optional components and mutually exclusive variants;
- export, edit, compare, and re-import assets through controlled workspaces;
- test a package against disposable or recoverable targets;
- publish a package with version, provenance, credits, and compatibility information;
- update a package without destroying older working versions.

The Manager must distinguish evidence from inference. A filename may suggest a character; it does not grant the application the ability to retarget arbitrary Unity data safely.

### Tool developers and maintainers

External tools should be integrated through explicit adapters with:

- project and author attribution;
- source and release links;
- version and platform information;
- declared license status;
- user-controlled installation or selection;
- bounded inputs and isolated outputs;
- no access to deployment state unless the integration genuinely requires it.

Credits are mandatory. Bundling, modification, and redistribution still require a compatible license or explicit permission.

## Product pillars

### 1. Automatic plumbing

Internal maintenance should happen automatically and visibly:

- installation detection;
- metadata preparation;
- imported-package preparation;
- source analysis;
- stale-cache refresh;
- migration of supported older state;
- provider detail hydration;
- update and compatibility checks.

The interface should describe progress and failures, not ask users to operate internal machinery.

### 2. Safe by default

No game-file mutation occurs without:

- a verified target;
- a closed-game check;
- a complete conflict plan;
- known source hashes;
- a recovery strategy;
- transactional staging;
- post-write verification.

Unknown state fails closed. User preferences may be quarantined and reset; critical deployment evidence may not be quietly discarded.

### 3. Immutable history

Imported versions remain immutable. Editing, updating, and conversion create new versions or generated workspaces.

This makes rollback possible, profile behavior reproducible, update comparison meaningful, provenance inspectable, and creator experimentation less destructive.

### 4. Creator-first metadata

A package should explain:

- who made it;
- what version it is;
- what characters, dresses, parts, and content types it affects;
- which game regions and builds it supports;
- what it requires or conflicts with;
- which options it exposes;
- how its files map to final targets;
- where it came from and how it may be redistributed.

The guided UI should cover common cases. The manifest remains available for advanced cases and automation.

### 5. Cross-platform parity

Windows, Linux, Steam, Proton, and supported regional installations are first-class targets.

Platform-specific behavior belongs behind platform services and packaging adapters, not scattered through UI callbacks. A feature is not complete merely because it worked once on the machine that wrote it.

### 6. Community interoperability

Uma Mod Manager should consume and produce understandable formats instead of trapping users in private state.

Examples include portable package manifests, external-tool JSON imports, profile export/import, CSV and diagnostic reports, generated creator workspaces, and documented provider/backend contracts.

## Near-term priorities

1. Finish automatic preparation and multi-target source handling on real packages.
2. Replace the current Library layout with a responsive, readable player-focused interface.
3. Make Inspect & edit a complete visual workflow for package targeting and compatibility.
4. Add friendly mod-creator documentation and sample packages.
5. Improve GameBanana discovery, file selection, updates, and package provenance.
6. Expand read-only asset and veteran-data tools through credited external adapters.
7. Convert legacy editing features into native generated-mod workflows.
8. Publish reliable Windows, Debian, and AppImage alpha channels with exact checksums and upgrade notes.

## Explicit non-goals

Uma Mod Manager is not intended to:

- bundle copyrighted game assets;
- distribute decrypted game databases;
- bypass purchases or platform ownership;
- modify accounts, currency, saves, rankings, or network traffic;
- accept arbitrary executable installers as ordinary mods;
- load unreviewed native plugins into the Manager process;
- claim safe support for unknown game builds;
- copy unlicensed community tools because a credits panel was added;
- hide uncertainty behind confident labels.

## Definition of success

The long-term measure is not the number of buttons, lines of code, or provider logos.

Success means:

- fewer broken installations;
- fewer installation tutorials consisting of unexplained file surgery;
- more reusable package metadata;
- more creators able to inspect and modify existing work;
- more distinct, maintained, credited mods available to players;
- safe restoration remaining boring even when everything else is experimental.

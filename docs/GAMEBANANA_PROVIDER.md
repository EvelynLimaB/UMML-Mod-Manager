# GameBanana provider behavior

Uma Mod Manager treats GameBanana as a remote provider, not as part of the
deployment engine. Provider failures must never alter the game installation or
leave a partially imported package behind.

## Catalogue and detail paths

Interactive browsing uses independent official GameBanana API surfaces:

1. the v11 Mod index for sorted catalogue pages and search;
2. the Core `List/New` endpoint when the v11 catalogue is unavailable;
3. the v11 Mod detail endpoint for complete submission metadata;
4. the Core `Item/Data` endpoint when v11 details are unavailable.

A temporary v11 circuit prevents every result from repeating the same failing
request during a provider outage. HTTP 429, 500, 502, 503, and 504 responses,
timeouts, temporary DNS failures, reset connections, and prematurely closed
responses receive a short bounded retry sequence.

The Manager does not loop indefinitely, silently change API hosts outside the
known provider set, or treat an HTML error page as JSON.

## Local catalogue cache

Successful catalogue pages and mod details are cached for at most fourteen days.
The cache:

- is stored below the normal user cache directory;
- is keyed by region, page, page size, sort, and query;
- uses atomic writes;
- rejects links, oversized files, malformed JSON, unknown cache versions, and
  expired records;
- contains public provider metadata only;
- is never treated as permission to deploy or overwrite game files.

When both live API paths are temporarily unavailable, Discover may show the most
recent valid cached page. Installing a cached result still refreshes its current
file details before downloading whenever a live provider path is available.

## Download strategy

GameBanana does not guarantee that an anonymous `/dl/<file-id>` or
`/mmdl/<file-id>` request returns raw archive bytes. Depending on the file,
server, region, and browser session, those routes may return an HTML landing or
anti-abuse page instead.

The Manager therefore uses two bounded paths:

1. **Direct provider transfer.** When the API supplies a usable HTTPS archive
   response, the Manager downloads it with verified TLS, streaming size limits,
   partial-file cleanup, SHA-256 calculation, and immutable source metadata.
2. **Browser-assisted transfer.** When the selected GameBanana route returns
   browser-only HTML, the Manager opens that exact GameBanana URL in the user's
   default browser. The browser keeps the user's normal cookies and executes the
   site's own JavaScript. The Manager watches the user's Downloads directory,
   ignores partial and unrelated files, verifies the expected file name, byte
   size, and MD5 when those values are available from the File API, and imports
   the completed archive with the original submission and file IDs.

The browser is launched outside PyInstaller/AppImage library overrides so the
host browser does not inherit bundled runtime libraries.

The Manager never disables TLS verification, executes HTML or JavaScript, or
accepts a third-party landing URL as a trusted archive source.

## Why mature managers use protocol integration

GameBanana's supported mod-manager model uses a registered custom URI scheme or
Remote Install connection. The site then sends the manager a payload containing
the actual archive URL, commonly in the form:

```text
manager-scheme:[URL_TO_ARCHIVE]
```

Hedge Mod Manager, Reloaded-II, and UKMM follow this model. Official
`uma-mod-manager:` registration is the intended long-term integration. The
browser-assisted path is the compatibility bridge until that registration is
available and configured on GameBanana.

## Watched download locations

On Linux the Manager checks the XDG Downloads directory and `~/Downloads`. On
Windows it checks the normal user Downloads directory. Testers can override the
location for one run with:

```bash
UMML_GAMEBANANA_DOWNLOAD_DIR=/path/to/downloads \
  ./umml-manager_0.2.0-alpha.21_x86_64.AppImage
```

The watched root must be a normal directory, not a symbolic link. Browser
partials such as `.crdownload`, `.part`, `.download`, `.partial`, and `.tmp` are
ignored. The default timeout is ten minutes. If the browser saves elsewhere,
the completed archive can still be imported through **Discover → Local
folders**.

## Security boundaries

- HTTPS certificate verification remains enabled.
- Provider cookies are ephemeral and memory-only.
- Direct transfers are size-limited and written atomically.
- Browser-assisted adoption rejects symlinks and unstable/partial files.
- Expected byte size and MD5 are checked when published by GameBanana's File
  API.
- Archive import retains traversal, link, duplicate-path, encryption, special
  file, expansion-size, and immutable-source protections.
- Failed or incomplete downloads are never installed.

## Deliberate limitations

- Full text search depends on GameBanana's searchable catalogue endpoint. During
  a v11 outage, the Core fallback can browse recent submissions and apply a
  local filter, but it cannot guarantee a complete historical search result.
- Cached metadata may be stale and is labelled as fallback data.
- Preview images are optional. Failure to load a preview does not block a mod
  detail page or file installation.
- GameBanana metadata is not proof that an uploaded archive is safe or compatible.
  Normal archive validation, immutable import, automatic preparation, conflict
  planning, and transactional deployment rules still apply.
- Official one-click registration is not yet configured on GameBanana, so some
  files require the browser-assisted bridge rather than a pure background
  transfer.

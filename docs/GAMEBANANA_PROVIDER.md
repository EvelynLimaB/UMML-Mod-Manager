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

## Downloads

File downloads:

- require verified HTTPS before and after redirects;
- use a `.part` file in the Manager download area;
- enforce declared and observed size limits;
- compute SHA-256 while streaming;
- require the received byte count to match a declared content length;
- retry only bounded transient failures;
- delete the partial file after every failed attempt;
- import only after the complete archive has been verified.

If GameBanana remains unavailable, the UI explains that no game files were
changed and offers the ordinary local-archive import path. A provider outage is
not a deployment emergency, however determined an HTTP 503 may sound.

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

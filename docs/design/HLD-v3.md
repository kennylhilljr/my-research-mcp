# Research MCP v2: High-Level Design (v3)

- **Date:** 2026-10-19
- **Requirements:** [PRD v3](../prd/PRD-v3.md) and its components; supersedes [HLD v2](HLD-v2.md)
- **Detail:** [LLD v3](LLD-v3.md)
- **Decisions:** [ADRs 0001 to 0012](../adr/)

## Changes from v2

Owner decisions of 2026-10-19, second round ([ADR 0012](../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md)): the design is domain-neutral (topic coverage is configuration); every endpoint v1 calls is kept; web search returns as an optional, capped source group (`web`: Vertex AI Search, Brave, SerpAPI, Programmable Search) that runs only on request, in fallback order by default (sections 4, 5 and 9). M0 is unchanged.

## Earlier changes (v2)

Owner decisions of 2026-10-19: cache retention is **120 days** instead of 30, and **archiving keeps a paper searchable**: only the PDF moves to Google Drive; extracted text, chunks, full-text entries and embeddings stay in `cache.db`, and a rebuild job can re-import the archive from Drive. See [ADR 0011](../adr/0011-archive-keeps-text-searchable-120-day-retention.md).

## 1. Scope

This document describes the shape of v2: the processes, the main components and how they talk, the data each owns, the security boundaries, and the key flows. Module names, schemas, signatures and the work breakdown are in the LLD.

## 2. System context

```
 +-------------------+   +-------------------+   +-------------------+
 | Claude Code       |   | Claude desktop    |   | OpenClaw agents,  |
 | (MCP client)      |   | (MCP client)      |   | Codex (MCP)       |
 +---------+---------+   +---------+---------+   +---------+---------+
           | stdio                 | stdio                 | stdio or loopback HTTP
           v                       v                       v
 +---------------------------------------------------------------------+
 | research-mcp stdio  (thin shim, one per client; no state)            |
 +----------------------------------+----------------------------------+
                                    | streamable HTTP, 127.0.0.1, bearer token
                                    v
 +---------------------------------------------------------------------+
 | research-mcpd  (one daemon per Mac, launchd KeepAlive)               |
 |  MCP endpoint /mcp  |  UI /ui  |  /healthz /readyz /api/status       |
 |  services: federation, works, cache, health, notify, jobs, scheduler |
 |  source registry (about 42 adapters)  |  shared async HTTP client    |
 |  stores: state.db, cache.db  |  workers (one subprocess per task)    |
 +---+--------------+-----------------+-----------------+--------------+
     |              |                 |                 |
     v              v                 v                 v
 Upstream APIs   macOS Keychain   Google Drive sync   macOS notifications,
 (arXiv, OpenAlex (secrets,       folder (archive)    OpenClaw inbox webhook
 Crossref, ...,   read only)
 upstream MCPs)
           ^
           | doctor (launchd: liveness every 15 min, full check daily; independent of the daemon)
```

Trust boundaries:

1. **Upstream content is untrusted.** Everything that comes from an API or a downloaded file is data; it is labeled untrusted when returned to a model.
2. **Local callers are authenticated.** Only the shim (with the bearer token) and the UI (with a session) can call the daemon.
3. **Secrets never leave the HTTP layer** except to the origin they belong to.

## 3. Component architecture

The daemon is one Python process built in layers. Each layer depends only on the layers below it.

```
 transport    mcp_app (tools, resources, prompts)      ui (pages)      http_api (status)
                 |                                        |                 |
 services     federation   works   cache   health   notify   jobs   scheduler
                 |            |       |       |        |
 sources      registry -> adapters (one module per source; SourceSpec)
                 |
 platform     http client (rate limits, retries, redaction, telemetry)   secrets (Keychain)
              stores (state.db, cache.db; migrations)   workers (subprocess per task)   settings   logging
 core         ids, models, errors, envelope, time (no I/O)
```

Rules ([ADR 0004](../adr/0004-modular-core-composition-root.md), [ADR 0005](../adr/0005-async-io-cpu-off-loop.md)):

- `core` has no I/O and no third-party service dependencies.
- Adapters translate only; they never retry, sleep, read secrets or write files ([ADR 0006](../adr/0006-source-adapter-contract.md)).
- Tools are thin: validate arguments, call one service, wrap the result in the envelope.
- One composition root, `build_app(settings)`, creates everything inside a lifespan. Nothing happens at import.
- Network I/O is async; CPU-heavy work (PDF parsing, chunking, embedding) runs in one short-lived subprocess per task, killed on timeout or memory limit; SQLite access runs in a thread with one writer per database.

## 4. Sources

- A **`SourceSpec`** declares each source: capabilities, identifier schemes, auth, rate policy, timeouts, page size, extras, probe, shutdown date, default enabled.
- An **adapter** implements `search`, `get`, `fulltext_candidates`, `citations` and `probe` for the capabilities it declares, returning normalized `WorkRecord`s with provenance.
- The **registry** discovers adapters, creates configured instances (four DSpace repositories, docs sites, Vertex AI Search engines), applies enable and disable settings, and answers "which sources can do X for group Y right now", combining configuration with live health.
- **Upstream MCP servers** (AWS Knowledge, Microsoft Learn) are adapters that use an MCP client instead of HTTP JSON.
- **Site sets** are named domain lists in configuration (v1's docs-domain list ships as `v1_docs`). Topic coverage, in any subject area, is added by configuring docs sites, site sets and search engines, not by code.
- **Web search** is the `web` group: four optional, metered sources, each off until configured and capped per day. It is never in the default fan-out.
- **Testing:** every adapter has seven recorded fixtures and runs through one conformance suite; an opt-in live check refreshes fixtures.

## 5. Federation and identity

```
 search(query, sources, filters, limit, cursor)
   -> registry.select(groups, filters, health)          # auto selection, skips down/unconfigured
   -> fan out: one task per source, per-source timeout, overall deadline
   -> per source: SearchPage(records, cursor) or SourceStatus(error)
   -> identity.resolve(records)                          # normalize ids, union-find on shared ids
   -> merge(records -> works), fuzzy merge flagged
   -> rank: reciprocal rank fusion + found-in-more-sources boost
   -> budget: trim to response budget, build combined cursor
   -> envelope {data: works, source_status: [...], next_cursor, truncated}
```

- **Identity:** `core.ids` normalizes identifiers (pure functions); `services/works.py` groups records by any shared identifier; if no identifier is shared, fall back to normalized title, year and first-author surname, flagged `fuzzy`.
- **`get_work`** resolves an identifier against every source that understands its scheme, merges the records, and adds open-access locations, integrity status and cache state.
- **The `web` group** runs in `fallback` order by default: the configured web sources are tried one at a time (Vertex, Brave, SerpAPI, Programmable Search) until one answers, so a request spends at most one paid query per page. With `strategy = "all"` they fan out like any other group. A `site_set` restricts the domains.
- **Citations, authors, cite and integrity** are services over the same registry and identity layer.

## 6. Retrieval and cache

```
 fetch(id or url)
   -> works.resolve -> OA locations from all sources -> choose by preference
   -> downloader: https, host policy per hop, public IPs only, byte cap, magic bytes, atomic write, sha256
   -> worker: extract (PyMuPDF, limits) -> chunk (token, section aware) -> embed (passage)
   -> cache.db: document (state=cached, expires_at=+120d), file, extraction, chunks, FTS, vectors
   -> envelope {doc_id, summary, pages, chunks, coverage}
```

The lifecycle state machine ([ADR 0007](../adr/0007-cache-lifecycle-and-drive-archive.md), [ADR 0011](../adr/0011-archive-keeps-text-searchable-120-day-retention.md)):

```
 cached -[3 days before expiry, daily 09:00]-> expiring -[archive]-> archived
   ^  |                                          |  |-[discard]-> discarded (7-day trash, notice 24 h before purge, then files removed)
   |  |-[pin]-> pinned                            |
   |                                             |-[no answer for 24 h]-> kept -[7 days]-> expiring
   |-[keep another 120 days]---------------------|
```

- **Archive** copies the file and a sidecar metadata JSON to the Drive sync folder, verifies the copy, then removes only the cached file. The document's text, chunks, full-text entries and embeddings stay in `cache.db`, so archived papers remain searchable and readable. If the folder is unavailable, it uses a local fallback and reconciles later. A rebuild job can re-import the archive from the Drive folder and its sidecars.
- **Metadata outlives files.** A discarded work keeps its citation snapshot and fetch recipe; an archived work keeps those plus its searchable text.
- **Local search** is hybrid: FTS5 BM25 plus exact vector similarity over embeddings stored in `cache.db`, fused by reciprocal rank ([ADR 0008](../adr/0008-sqlite-stores-and-vectors.md)).

## 7. Health, credentials and notifications

```
 HTTP client --telemetry--> state.db.calls --rollup--> source_health
 scheduler --probes--> adapters.probe() ----------------^
 secrets --metadata--> state.db.credentials <-- passive headers (GitHub expiry, rate limits)
 health.evaluate() -> source and credential states -> diff -> notify (macOS, OpenClaw webhook, UI banner)
 doctor (launchd: liveness every 15 min, full daily) -> same checks without the daemon -> notify on change
```

- **States** follow [PRD-health](../prd/components/PRD-health-v1.md) section 2.
- **Notifications** fire on state changes and roll unresolved items into a daily digest, with quiet hours.
- **Federation** consults health before selecting sources.

## 8. Local UI

- **Stack:** Starlette routes and Jinja2 templates in the daemon, with a vendored htmx file for partial refresh and confirmation dialogs ([ADR 0010](../adr/0010-localhost-ui-stack.md)).
- **Data access:** pages read the same services the MCP tools use, so there is no second API.
- **Sessions:** a session starts from a one-time token URL. All writes need CSRF tokens and confirmation.
- **Pages:** source board, credentials, quota, jobs, cache, review, archive, maintenance, events, settings.

## 9. Security architecture

| Threat | Control |
|---|---|
| Prompt-injected model tries to read local files | No SQL tool; no caller-chosen paths; files only under the cache root; DuckDB (if used internally) locked down ([ADR 0009](../adr/0009-no-sql-untrusted-content.md)). |
| Prompt-injected model tries to delete data | No hard delete in MCP; the only MCP discard is a review decision inside an open batch, recorded as an agent decision, sent to a 7-day trash and announced to the owner at once with an undo link; the owner is notified again 24 hours before any purge; annotations mark state-changing tools. |
| Secret leaks into chat or logs | Keychain (the Google sign-in excepted, see below); `Secret` type; origin-scoped attachment; header placement; one redaction filter on logs, errors, UI and notifications; errors carry codes, not exception text. |
| Paid web-search spend runs away | Web sources off until configured, never in the default fan-out, fallback order (one paid query per page), daily caps that switch a source to `budget_exhausted`. |
| Google sign-in token misuse | `gcloud` owns the sign-in; v2 holds only a short-lived access token in memory and attaches it only to `discoveryengine.googleapis.com`. |
| SSRF and hostile downloads | One downloader: https, per-hop host policy, public IPs only with the connection pinned to the checked IP (no second DNS lookup), byte cap, magic bytes, atomic write. |
| Hostile PDFs | Parsing in a separate subprocess per document with a CPU limit, an RSS watchdog, a wall-clock timeout and a page cap; a crash affects only that document. |
| Other local processes call the daemon | Loopback only, bearer token, Host and Origin checks; UI session cookie plus CSRF. |
| Upstream drift returns wrong data | Probes check response shape; fixtures pinned in tests; per-source disable. |
| Supply chain | Lock file, weekly dependency audit, SHA-pinned CI actions, secret scan. |

## 10. Data stores

| Store | Location | Owns | Backed up |
|---|---|---|---|
| `state.db` (SQLite, WAL) | `~/Library/Application Support/research-mcp/` | Credential metadata, source health, call telemetry and rollups, searches, jobs, schedule runs, notifications, review batches and a copy of review events | Nightly, 7 kept |
| `cache.db` (SQLite, WAL, FTS5, vector BLOBs) | `~/Library/Application Support/research-mcp/cache/` | Works, identifiers, source records, documents and lifecycle (including pins, decisions and archive paths), files, extractions, chunks, FTS, embeddings, collections, outbox | Nightly, 7 kept |
| Files | `~/Library/Application Support/research-mcp/cache/files/` (by SHA-256) and `trash/` | Cached PDFs and HTML | No (re-fetchable; archived copies live in Drive) |
| Model cache | `~/Library/Caches/research-mcp/models/` | Embedding model files | No (re-downloadable) |
| Archive | Drive sync folder `My Drive/Research Archive/<year>/` | Archived files and sidecars (their text stays in `cache.db`) | By Google Drive; also the source for the archive rebuild job |
| Config | `~/.config/research-mcp/config.toml` | Settings and secret references | Nightly with `state.db` |
| Secrets | macOS login Keychain, `research-mcp/<NAME>` | Credential values and the daemon token | By Keychain |

Nothing the lifecycle depends on lives in `~/Library/Caches`, which macOS and cleaning tools may purge. Both databases are backed up; only re-fetchable files are not.

## 11. Key flows

### 11.1 Cross-source search

1. The agent calls `search("policy-as-code adoption", sources="auto", filters={year_from: 2023})`.
2. The registry selects `openalex`, `crossref`, `semantic_scholar`, `arxiv`, `core`, `dblp` and `ssrn` from the default groups, and reports `ads` as `disabled`. (Had OpenAlex's budget been spent, it would be reported `skipped_budget` instead of selected.)
3. Seven tasks run with 5 s source timeouts inside an 8 s deadline.
4. The returned records are normalized, grouped by shared identifiers, merged and ranked.
5. The agent gets 20 works with `found_in`, plus seven `source_status` entries; one says `timeout`.

### 11.2 Fetch and read

1. `fetch("doi:10.1145/3649835")` resolves OA locations from Unpaywall, OpenAlex and the publisher, picks the best one and downloads it safely.
2. A worker extracts, chunks and embeds the document.
3. The document is stored as `cached` until a date 120 days out.
4. `read(doc_id, pages="3-5")` returns a bounded window with a cursor.

### 11.3 Expiry review and archive

1. At 09:00 the scheduler finds 6 documents expiring within 3 days and creates batch `rb-2026-11-14`.
2. The owner gets one macOS notification.
3. Clicking it opens `/ui/review/rb-2026-11-14`. The owner archives 2, discards 3 and leaves 1 unanswered.
4. The archive job copies 2 files plus sidecars to Drive, verifies them, and removes the cached PDFs; both papers stay searchable through their text in `cache.db`.
5. The 3 discards go to the trash for 7 days.
6. When the batch closes 24 hours later, the unanswered item becomes `kept` and is asked about again on 2026-11-22.

### 11.4 Credential expiring

1. A GitHub call returns `GitHub-Authentication-Token-Expiration` 13 days out, and the credential becomes `expiring_soon(13)`.
2. The state change produces a notification: "GitHub token expires in 13 days: rotate in Keychain item research-mcp/GITHUB_TOKEN".
3. Clicking it opens the Credentials page, which links to GitHub's token page and shows the value-free `security` command.
4. After rotating, the owner presses "Reload credentials". The fingerprint changes, the next call shows the new expiry, and the state returns to `ok`.

## 12. Deployment and operations

| Topic | Approach |
|---|---|
| **Install** | `uv tool install` (or a venv) for the package, then `research-mcp install`. Install writes three LaunchAgents (`local.research-mcpd` with KeepAlive; `local.research-mcp-watchdog` every 15 minutes; `local.research-mcp-doctor` daily at 08:52), creates the folders, generates the daemon token in Keychain, makes the first archive write in the foreground (for the macOS privacy prompt), and prints the client configs. |
| **Upgrade** | `research-mcp upgrade` with rollback on a failed `doctor`. |
| **Logs** | JSON lines with rotation. The UI shows recent warnings and errors. |
| **Backups** | Nightly copy of `state.db`, `cache.db` and the config. |
| **Parallel run with v1** | v1 stays installed under its old client entry, disabled at cutover, until retirement ([ADR 0001](../adr/0001-new-repo-v1-read-only.md)). |

## 13. Quality attributes

| Attribute | How it is met |
|---|---|
| Maintainability | One adapter module per source; conformance suite; generated inventory; strict typing; no module over about 400 lines. |
| Reliability | Per-source isolation in fan-out; retries with backoff; circuit-breaking through health states; worker isolation for parsing. |
| Performance | Concurrent fan-out with deadlines; shared connection pools; response budgets; FTS5 and exact vectors at personal-corpus scale (thousands of chunks). |
| Observability | Call telemetry, probes, states, notifications, structured logs, status endpoints, UI. |
| Security | Section 9. |
| Cost | Global rate limits and budgets for metered sources; quota states; no paid search providers. |

## 14. Milestones and where they land

| Milestone | Components built |
|---|---|
| M0 | core, platform (settings, secrets, HTTP, downloader, stores, logging, jobs, scheduler), sources (contract, registry, arXiv, Crossref, OpenAlex), federation, tools `search`, `get_work`, `list_sources`, daemon, shim, install, CI |
| M1 | all other adapters; citations, authors, cite, integrity; health, credentials, notifications, doctor |
| M2 | workers, extraction, cache lifecycle, review, searchable archive and its rebuild job, collections, crawl jobs, disk and integrity checks |
| M3 | UI |
| M4 | secrets import, legacy import, client cutover, v1 retirement |

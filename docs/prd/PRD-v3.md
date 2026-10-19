# Research MCP v2: One Tool, Many Sources (PRD v3)

- **Owner:** Kenny Hill
- **Status:** Draft for owner review
- **Date:** 2026-10-19
- **Repository:** `my-research-mcp-v2` (new); v1 is `my-research-mcp-server`, read-only until cutover
- **Inputs:** [Deep review v1](../review/REVIEW-v1.md) and its three findings files; supersedes [PRD v2](PRD-v2.md)
- **Design:** [HLD v3](../design/HLD-v3.md), [LLD v3](../design/LLD-v3.md); **tests:** [TEST-PLAN v3](../test-plan/TEST-PLAN-v3.md); **decisions:** [ADRs](../adr/)

## Changes from v2

Owner decisions of 2026-10-19, second round ([ADR 0012](../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md)):

1. **Domain-neutral.** No goal, requirement or tool is tied to one subject area. Coverage of any area comes from configuration (docs-site instances, site sets, web-search engines), so it can grow without a requirements change.
2. **Every endpoint v1 calls is kept** (the AWS and Microsoft Learn site-search endpoints were already replaced by the vendors' official MCP servers). The v1 docs-domain list and crawl projects ship as default configuration.
3. **Web search returns as an optional source group (`web`):** Vertex AI Search (`vertex_search`), Brave, SerpAPI and Google Programmable Search. Each is off until configured, capped per day, and used only when asked for. Open decision O1 is closed. The catalog grows from 38 to 42 sources.
4. M0 is unchanged.

Earlier changes (v2, [ADR 0011](../adr/0011-archive-keeps-text-searchable-120-day-retention.md)): cache retention is 120 days; archived papers keep their text and embeddings and stay searchable.

## 1. Summary

Research MCP is a personal MCP server that lets Claude, Codex and OpenClaw agents search, fetch, read and cite research from many sources through one MCP server. v2 is a rebuild. It keeps the breadth of v1 (about 25 sources) and grows it to 42 (including optional, capped web-search sources), but puts every source behind one adapter contract, searches them together, shows the health of each one, warns the owner before a credential expires, and treats downloaded papers as a 120-day cache that asks before anything is deleted; archived papers move to Google Drive and stay searchable. A small local web page shows all of it.

## 2. Problem

1. **Reach is there but hard to use.** v1 has 53 single-source tools. A question that spans sources takes 10 to 20 tool calls with different argument names and result shapes, and the same paper comes back several times.
2. **Breakage is silent.** Three sources are degraded by upstream changes today (OpenAlex, Semantic Scholar, Crossref) and one has an announced shutdown (Google Programmable Search, 2027-01-01). Nothing in v1 noticed.
3. **Credentials are invisible.** Keys sit in plaintext in three MCP client configs, can leak into chat through error messages, and nobody is told when one expires or stops working.
4. **It is hard to change.** Everything is in one 4,613-line file; adding a source touches five places.
5. **It is unsafe in ways that matter on a personal Mac:** arbitrary local file reads through SQL, keys sent to third-party hosts, downloads that go anywhere.
6. **The local corpus grows without purpose.** Papers are fetched for one-off needs but kept forever, duplicated, and never cleaned up.

## 3. Goals and non-goals

### 3.1 Goals

| ID | Goal | Measure |
|---|---|---|
| G1 | **Breadth.** Keep every source and endpoint v1 calls, and add the high-value ones found in the review. Coverage is not limited to any subject area; new areas are added by configuration. | At least 42 sources registered at the end of M1; each listed on the source board; every v1 endpoint mapped to a v2 source. |
| G2 | **One search.** A single call searches many sources at once and returns merged, deduplicated results with per-source status. | A five-source search returns in under 8 s at p95 with every source's status reported. |
| G3 | **Cheap to maintain.** Adding, fixing or disabling a source is isolated to one module plus fixtures. | A new source needs one adapter file and one fixtures folder; no other hand-written file changes. |
| G4 | **Monitored.** The owner can see, at a glance, which sources work, which are degraded or down, and why. | Every source has a probe; a detected state change reaches the owner within 15 minutes (outside quiet hours); a dead daemon is reported within 15 minutes by the watchdog. |
| G5 | **Credential care.** The owner is told before a credential expires and when one stops working, with the fix. | Expiring notices at 14, 7, 3 and 1 days; invalid notices within one probe cycle. |
| G6 | **Cache, not library.** Fetched items live 120 days, then the owner chooses archive or discard; nothing is deleted without an answer. Archived items stay searchable. | Zero items deleted without a recorded owner decision. |
| G7 | **Safe by default.** No local file read beyond the cache, no credential sent outside its origin, no secret in any output or log. | Security test suite green; secret-leak tests cover every error path. |
| G8 | **Visible.** A local web page shows sources, credentials, quotas, jobs and the cache. | UI pages in [PRD-ui](components/PRD-ui-v1.md) all render from live state. |

### 3.2 Non-goals

- A curated paper library, reference manager or note-taking tool (Zotero does that).
- Remote or multi-user access. The server binds to loopback on the owner's Mac.
- Scraping Google Scholar. (Paid web-search providers are allowed only as optional sources with a daily cap.)
- Limiting coverage to one subject area.
- Free-form SQL over local files.
- Keeping v1 tool names or result shapes. Clients are updated at cutover.

## 4. Users and surfaces

| User | Surface | Typical use |
|---|---|---|
| The owner, through an agent (Claude Code, Claude desktop, Codex, OpenClaw agents) | MCP tools, resources and prompts over stdio (through a shim) or loopback streamable HTTP | "Find recent work on retrieval-augmented generation evaluation across arXiv, ACM and SSRN, then pull the three best open-access PDFs and summarize them." |
| The owner, directly | Local web UI at `http://127.0.0.1:<port>` | Check the source board, reload a key after rotating it in the Keychain, answer the "archive or discard" review. |
| The owner, passively | macOS notifications; optional OpenClaw inbox message | "GitHub token expires in 7 days", "OpenAlex is rate limited", "6 cached papers expire Friday: review". |
| The ECC orchestrator and coding agents | The repository and its docs | Build v2 one work unit at a time (LLD section 12). |

## 5. Scope by component

Each component has its own PRD with numbered requirements. The parent holds goals, cross-cutting rules and milestones; components hold the detail.

| Component | PRD | Requirement prefix | One line |
|---|---|---|---|
| Sources | [PRD-sources-v2](components/PRD-sources-v2.md) | FR-SRC | The adapter contract, the source registry, the list of 42 sources, site sets and the optional web-search group. |
| Search and identity | [PRD-search-v1](components/PRD-search-v1.md) | FR-SRCH | Federated search, `get_work`, identifier normalization, dedupe, citations and integrity checks. |
| Retrieval and cache | [PRD-cache-v2](components/PRD-cache-v2.md) | FR-CACHE | Fetch, read, cite, local search, the 120-day lifecycle, the owner review and the searchable Drive archive. |
| Health and credentials | [PRD-health-v2](components/PRD-health-v2.md) | FR-HLTH | Probes, source and credential states, quotas, notifications and `doctor`. |
| Local UI | [PRD-ui-v2](components/PRD-ui-v2.md) | FR-UI | The read-mostly localhost web page. |
| Platform and security | [PRD-platform-v2](components/PRD-platform-v2.md) | FR-PLAT | Daemon, shim, Keychain secrets, HTTP client, logging, output bounds, packaging and CI. |
| Migration and cutover | [PRD-migration-v3](components/PRD-migration-v3.md) | FR-MIG | Credential import, optional corpus import, client cutover and v1 retirement. |

## 6. Cross-cutting requirements

| ID | Requirement |
|---|---|
| NFR-01 | **Single process.** One daemon per Mac owns all HTTP clients, rate limiters, stores and the scheduler. MCP clients connect through a thin stdio shim or loopback HTTP ([ADR 0002](../adr/0002-one-daemon-with-stdio-shims.md)). |
| NFR-02 | **Async.** No tool blocks the event loop. Network I/O is async; PDF parsing, extraction and embedding run in worker processes ([ADR 0005](../adr/0005-async-io-cpu-off-loop.md)). |
| NFR-03 | **No secrets at rest outside the Keychain.** Config files hold references only; this includes the daemon token and any webhook token ([ADR 0003](../adr/0003-secrets-in-keychain.md)). The one exception is the owner's Google sign-in for Vertex AI Search, which `gcloud` stores and v2 never copies ([ADR 0012](../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md)). |
| NFR-04 | **No secret in any output.** Tool results, errors, logs, UI pages, notifications and test snapshots never contain a secret value. |
| NFR-05 | **Bounded output.** Every tool result fits a byte budget (default 64 KB) and pages with a cursor beyond it. |
| NFR-06 | **Untrusted content is labeled.** Text fetched from the internet is returned inside an envelope marked untrusted ([ADR 0009](../adr/0009-no-sql-untrusted-content.md)). |
| NFR-07 | **Loopback only.** Nothing listens on a non-loopback address; every HTTP request except the `/healthz` and `/readyz` checks needs a bearer token or a UI session. |
| NFR-08 | **Respect upstream terms.** Per-source rate limits are global across clients; contact email and user agent are sent where asked; arXiv's 1 request per 3 seconds is honored. |
| NFR-09 | **Testable offline.** The default test run makes no network calls. Live checks are opt-in. |
| NFR-10 | **Docs follow code.** Tool and source inventories are generated from the registry, never hand-maintained. |
| NFR-11 | **Prose style.** Documents and UI text use no em dashes or en dashes. |

## 7. Success metrics (measured 30 days after cutover)

| Metric | Target |
|---|---|
| Tool calls per cross-source question | 1 to 3 (v1: 10 to 20) |
| Sources registered | 42 or more |
| Source state changes noticed by the owner before an agent hit them | 90% or more |
| Credentials that expired without a prior notice | 0 |
| Items deleted without an owner decision | 0 |
| Test coverage on `src/` | 85% or more; every adapter has contract tests |
| Time to add a new free source (owner estimate, agent-built) | One work unit |

## 8. Architecture at a glance

See [HLD v3](../design/HLD-v3.md). In short: a launchd daemon (`research-mcpd`) runs one Python process with a source registry of adapters, a federation service, a cache with lifecycle, a health service and scheduler, two SQLite files (`state.db`, `cache.db`, both in Application Support and backed up nightly), the MCP endpoint and the web UI. Clients start `research-mcp stdio`, a shim that relays to the daemon.

## 9. Decisions recorded as ADRs

| ADR | Decision |
|---|---|
| [0001](../adr/0001-new-repo-v1-read-only.md) | v2 is a new repository; v1 stays read-only and running until cutover. |
| [0002](../adr/0002-one-daemon-with-stdio-shims.md) | One daemon per Mac; clients use a stdio shim. |
| [0003](../adr/0003-secrets-in-keychain.md) | Secrets live in the macOS Keychain; config holds references. |
| [0004](../adr/0004-modular-core-composition-root.md) | Modular core built by one composition root; no work at import. |
| [0005](../adr/0005-async-io-cpu-off-loop.md) | Async I/O end to end; CPU work in worker processes. |
| [0006](../adr/0006-source-adapter-contract.md) | Every source is an adapter with a declarative `SourceSpec`. |
| [0007](../adr/0007-cache-lifecycle-and-drive-archive.md) | Cache with owner review; archive to the Google Drive sync folder (amended by 0011). |
| [0011](../adr/0011-archive-keeps-text-searchable-120-day-retention.md) | 120-day retention; archived papers keep their text and embeddings and stay searchable. |
| [0012](../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md) | Requirements are domain-neutral; every v1 endpoint is kept; web search is an optional, capped source group. |
| [0008](../adr/0008-sqlite-stores-and-vectors.md) | Two SQLite files; vectors stored in SQLite, not a persisted DuckDB index. |
| [0009](../adr/0009-no-sql-untrusted-content.md) | No free-form SQL; fetched content is labeled untrusted. |
| [0010](../adr/0010-localhost-ui-stack.md) | The UI is server-rendered (Starlette, Jinja2, htmx) inside the daemon. |

## 10. Milestones

| Milestone | Outcome | Exit |
|---|---|---|
| **M0 Foundation** (ECC pilot) | Repo, settings, Keychain secrets, safe HTTP client with redaction, state store, adapter contract and registry, three reference adapters (arXiv, Crossref, OpenAlex), federated `search`, `get_work`, `list_sources`, daemon, stdio shim, launchd install, CI. | All M0 tests green; a client can search three sources through the shim on the owner's Mac. |
| **M1 Reach and health** | Every remaining v1 source ported and the new sources added, each with fixtures and a probe; citations, integrity checks; health states, credential states, quota tracking, notifications, `doctor`. | 42 or more sources registered, every v1 endpoint mapped; source board data available through `research://sources`; notifications verified on the Mac. |
| **M2 Retrieval and cache** | `fetch`, `read`, `search_cache`, `cite`, collections, extraction and chunking, embeddings, the 120-day lifecycle, the review, the searchable Drive archive and its rebuild job, disk monitoring. | Lifecycle tests green; one real archive written to Drive and verified. |
| **M3 Local UI** | All UI pages. | UI acceptance tests green; owner walkthrough. |
| **M4 Cutover** | Credential import from v1 client configs into Keychain, optional corpus import, client configs switched, v1 stopped. | 14 days of daily use on v2 with no fallback to v1; then v1 archived. |

## 11. Open decisions for the owner

From the [review](../review/REVIEW-v1.md) section 7, plus two raised while writing the components:

| # | Decision | Recommendation |
|---|---|---|
| O1 | Remove the web-search providers, or keep them. | Closed: keep all four as optional, capped sources (ADR 0012). |
| O2 | Register free OpenAlex and Semantic Scholar keys. | Yes. |
| O3 | PDF parser. | PyMuPDF in a worker process. |
| O4 | Any SQL or dataset tool. | None in the first release. |
| O5 | Second notification channel. | OpenClaw inbox through a webhook. |
| O6 | AWS and Microsoft Learn MCP servers through v2 or separately. | Through v2. |
| O7 | Fixed 120 days from fetch, or 120 days from last use. | Fixed from fetch; predictable. |
| O8 | Review timing: ask 3 days before expiry; re-ask unanswered items after 7 days; discards go to a 7-day trash. | Accept. |

## 12. Risks

| Risk | Mitigation |
|---|---|
| Upstream APIs change faster than one person can follow. | Probes check response shape, not just status; recorded fixtures make breakage visible in tests; each source can be disabled with a flag. |
| Metered sources (OpenAlex budget, web-search providers) run out mid-task or cost more than expected. | Budget tracking with `quota_low`, `rate_limited` and `budget_exhausted` states; federation skips exhausted sources and says so; web-search sources are off until configured, capped per day, and never in the default fan-out. |
| Keychain locked or unreadable (for example right after login). | Reads go through `/usr/bin/security` with a timeout; a locked Keychain is one `keychain_locked` state and one notification, not a notice per key; `doctor` gives the fix. |
| Drive sync folder unavailable, blocked by macOS privacy controls, or not uploading. | Install performs the first archive write in the foreground so the privacy prompt appears; `doctor` checks access; local fallback with a warning and reconcile; nothing leaves the cache until the archive copy is verified; upload state is checked and a stalled upload is reported. |
| PyMuPDF crashes on hostile PDFs. | Parsing in a worker process with CPU, memory, page and time limits. |
| Scope creep toward a library manager. | Non-goals in section 3.2; collections stay minimal. |

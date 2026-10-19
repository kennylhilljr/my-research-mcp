# Research MCP v1: Architecture and Maintainability Review

Scope: architecture, module boundaries, concurrency, configuration, error and result shapes, typing, tests, packaging, CI, and developer experience. Reviewed the read-only copy at `/home/claude/review/v1`. The code was not modified; tests, ruff, mypy and coverage were run against a scratch copy in an isolated virtualenv (mcp 1.30.0, pymupdf 1.28.2, duckdb 1.5.6, Python 3.11; fastembed not installed).

Owner priority applied when weighting findings: the value of the server is horizontal reach across many sources, and stored papers are a one-off cache. Findings that make adding, fixing, disabling, or fanning out across sources expensive are ranked highest.

No credentials were found in the repository (pattern scan for Google, GitHub, OpenAI, Brave, and Slack token shapes returned nothing).

---

## 1. Current architecture

### 1.1 Shape

```
                         +------------------------------------------------------+
  MCP client  <--stdio/SSE-->  server.py  (4,613 lines, imported as top-level   |
                         |      module "server"; FastMCP("my-research") at :612) |
                         |                                                      |
                         |  module-level config: 17 os.environ reads at import  |
                         |  logging.basicConfig at import (:60)                 |
                         |  globals: _index, _duckdb_conn, _embed_model,        |
                         |           _vertex_ai_creds, 3 rate-limiter closures  |
                         |                                                      |
                         |  53 @mcp.tool functions (49 sync, 4 async)           |
                         |   |                                                  |
                         |   +-- 49 "legacy" tools: inline requests.get/post    |
                         |   |     (43 call sites), inline parsing, inline       |
                         |   |     error shaping, json.dumps(indent=2)           |
                         |   |                                                  |
                         |   +-- 4 "modern" tools (:4342-4595) -> research_mcp/ |
                         |         adapters (async def, but sync requests)      |
                         |                                                      |
                         |  PaperIndex (SQLite FTS5: papers, chunks) :76-438    |
                         |  PDF extract/chunk (PyMuPDF) :445-528                |
                         |  DuckDB in-memory conn, ATTACH sqlite + emb file     |
                         |  fastembed model (lazy)                              |
                         +------------------------------------------------------+
                                     |  imports only:
                                     v
   research_mcp/  (half-migrated "modern" layer, 1,902 lines)
     adapters/base.py, europe_pmc, opencitations, retractions, clinical_trials  USED
     models.py (SearchRequest, WorkSummary, Provenance)                          USED
     adapters/datacite.py                                                        UNUSED
     config.py, errors.py, cache.py, jobs.py, repository.py, security.py,
     prompts.py                                                                  UNUSED in prod (tests only)
```

### 1.2 What server.py contains, by section

| Lines | Section | Tools |
|---|---|---|
| 1-72 | imports, env config, logging | 0 |
| 73-440 | `PaperIndex` (SQLite FTS5, query sanitizer) | 0 |
| 441-530 | PDF text extraction and chunking | 0 |
| 531-607 | arXiv helpers, rate limiter | 0 |
| 608-986 | MCP instance, arXiv, download, index, local FTS, management | 10 |
| 987-1139 | Semantic Scholar | 2 |
| 1140-1603 | DSpace 8 helpers + 4 repos x (search, get) | 8 |
| 1604-2008 | DOI: Crossref, DataCite, Unpaywall, citation, OA download | 4 |
| 2009-2271 | OpenAlex | 3 |
| 2272-2492 | OSF / PsyArXiv via SHARE | 2 |
| 2493-2735 | CORE | 3 |
| 2736-2974 | Cloud docs (AWS, GCP, MS Learn, page fetch) | 4 |
| 2975-3605 | IAM docs: 4 web-search providers + crawler into paper FTS | 4 |
| 3606-3768 | GitHub | 3 |
| 3769-3979 | DuckDB analytics | 3 |
| 3980-4181 | Embeddings (fastembed + DuckDB VSS) | 3 |
| 4182-4596 | Adapter-backed tools (Europe PMC, retractions, citations, trials) | 4 |
| 4597-4613 | argparse entry point | 0 |

### 1.3 Key observation

There are two architectures in one repository. The running server is the monolith. The `research_mcp` package holds a typed domain model, a versioned repository, a security module with a hardened downloader, an error taxonomy, a job service and a cache, and almost none of it is wired in. Only the adapter base, four adapters and `SearchRequest` are imported (server.py:4191-4196). Two of the test modules target a `research_mcp.federation` and `research_mcp.server.build_mcp` that do not exist and are skipped at module level.

---

## 2. Findings

Severity reflects impact on v2 maintainability, weighted toward source isolation and federation.

| ID | Sev | Evidence (file:line) | Problem | Recommendation for v2 |
|---|---|---|---|---|
| ARCH-01 | critical | server.py:1-4613; section banners at :72, :441, :531, :608, :987, :1140, :1604, :2009, :2272, :2493, :2736, :2975, :3606, :3769, :3980, :4182 | One 4,613-line module holds transport, config, persistence, PDF parsing, 15+ source clients, 53 tools and the entry point. Any change to one source means editing and re-reviewing the monolith; merge conflicts and blast radius are maximal. | Split into composition root, core, http, sources (one module per source), federation, library (cache), tools. See section 3. No module over ~400 lines. |
| ARCH-02 | critical | research_mcp/config.py, errors.py, cache.py, jobs.py, repository.py, security.py, prompts.py, adapters/datacite.py: zero imports from server.py (only server.py:4191-4196 import adapters + `SearchRequest`). Coverage: cache 0%, config 0%, errors 0%, jobs 0% | Half-migrated "modern" layer. Roughly 1,300 lines of tested-in-isolation code (Settings, ResearchError taxonomy, SQLiteRepository, download_pdf_atomic, validate_url, JobService, SemanticCache, prompts, DataCite adapter) never runs. Readers cannot tell which path is authoritative, and fixes land in one path but not the other. | v2 should have exactly one implementation of each concern. Port the good pieces deliberately (security.py downloader and URL policy, repository.py schema, adapters' cursor envelope, ErrorCode enum) and delete the rest. Do not carry both layers forward. |
| ARCH-03 | critical | mcp 1.30 `func_metadata.call_fn_with_arg_validation` calls sync tools directly (`return fn(**args)`, no thread offload). server.py has 49 sync tools, 43 `requests.get/post` call sites, `time.sleep` at :541, :1004, :3178, :3513. Async tools :4343, :4396, :4455, :4524 await adapters whose `get_json` is sync (adapters/base.py:104-118 via `_AdapterHTTPClient`, server.py:4219-4228); `get_citations` calls `adapter.get_json` directly at :4494; `check_retractions` runs `_check_one_doi` serially at :4433 | Every tool call blocks the event loop. A 6.5 s CORE rate-limit sleep, a 120 s PDF download, a 500-page IAM crawl (:3442) or `index_all_papers` (3 s sleep per paper, :829) freezes all other requests, pings and cancellations. The "async" adapters are async in name only. Federated fan-out is impossible on this model. | Async end to end: one shared `httpx.AsyncClient` behind an `HttpPort`, async token-bucket rate limiter, `anyio.to_thread.run_sync` for CPU or blocking libraries (PyMuPDF, DuckDB, fastembed, sqlite). Long operations become jobs with progress via `Context.report_progress`. Enable ruff `ASYNC` rules in CI. |
| ARCH-04 | high | DSpace: 8 copy-paste tools for 4 repos (:1433-1601), MIT alone exposes `search_field` (:1434-1471). IAM web search: 4 provider branches inline in one tool (:3264-3340). Adapter-backed tools still hand-flatten `WorkSummary` in server.py (:4384-4394, :4569-4586). No registry, no `SourceSpec`, no enable/disable switch | No source abstraction for 30 of 34 external-source tools. Each tool re-implements URL, params, parsing, errors and output shape. Adding a source today touches: constants + env read, helper parser, one or more `@mcp.tool` functions with long docstrings, tests that patch `server.requests.get`, README tool table, CLAUDE.md and AGENTS.md (near-identical copies, both with hard-coded "53 tools"), CHANGELOG. Disabling a broken source requires a code edit. | One adapter module per source implementing a `SourceAdapter` port, plus a declarative `SourceSpec` (auth env vars, rate limit, quota, timeout, max page size, capabilities, id schemes, health probe, optional extra deps, enabled flag). A registry builds tools and `list_sources` from specs. DSpace becomes one adapter with four config instances. IAM web search becomes one adapter with provider strategies. |
| ARCH-05 | high | No fan-out code anywhere. `SearchRequest.sources` (models.py:204) is unused. tests/test_modern_mcp.py:14-28 imports nonexistent `research_mcp.federation`. 53 tools exposed (CLAUDE.md inventory) | No federated search. The model must call N per-source tools serially, reconcile duplicates itself, and has no per-source status, timeout, or partial-result signal. 53 tool schemas also consume a large share of client context. | `FederatedSearch` service: concurrent fan-out with per-source timeout and an overall deadline, cancellation of stragglers, per-source status (`ok`, `timeout`, `rate_limited`, `error`, `unconfigured`, `disabled`), dedupe by normalized identifiers (DOI, arXiv, PMID, OpenAlex), merged ranking and per-source cursors. Collapse the source tools into a small surface: `search`, `get_record`, `list_sources`, `get_citations`, `check_retractions`, `fetch_doc_page`. |
| ARCH-06 | high | 43 raw HTTP calls; timeouts 30 s (38x), 120 s (3x), 60 s, 20 s. Retry only for Semantic Scholar 429 (:996-1009). Rate limiters only for arXiv, S2, CORE (:545, :993, :2503) using a non-thread-safe closure (:535-543). User-Agents differ: :1965 `research-mcp/1.0`, :2755 `my-research-mcp-server/2.0 (+docs-search)` reused for IAM sites, :3627, :4199; most calls (Crossref, OpenAlex raw calls, DSpace, SHARE, MS Learn) send none. No `requests.Session`, so no connection pooling | HTTP policy is duplicated and inconsistent. No retry on 5xx, no `Retry-After` handling except S2, no polite-pool headers for Crossref, no per-host quotas, no response byte caps on most calls. Fixing a cross-cutting behavior means editing dozens of sites. | `HttpPort` owns: base timeouts, retries with jittered backoff on 429/5xx honoring `Retry-After`, per-source rate limit and concurrency from `SourceSpec`, streaming byte caps, one UA template with contact email, structured logging and metrics per source, and secret redaction (ARCH-08). Adapters never import an HTTP library. |
| ARCH-07 | high | Four error styles: (a) raise and let FastMCP turn it into text: `search_arxiv` :693, `search_semantic_scholar` :1050, `search_crossref` :1776, `search_openalex` :2166, `_share_search` :2384, `search_core` :2611; (b) `{"error": str}`: cloud and GitHub tools; (c) DSpace `{"error","status_code","source","hint"}` :1258-1278; (d) `AdapterError` strings :4378. errors.py taxonomy unused. 61 `"error"` literals, 34 `except Exception`. Success shapes vary: `entries` vs `results`, `results_count` vs `count`, `total_results` vs `total_count`; ids named `paper_id`, `openalex_id`, `core_id`, `uuid`, `id`, `nct_id`, `arxiv_id`. `get_doi_citation` returns raw text (:1834-1836). All 53 tools return `str` of `json.dumps(indent=2)` (99 occurrences) | Clients cannot program against results or errors. Retryability, rate limiting and "not configured" are indistinguishable. Pretty-printed JSON strings waste tokens and bypass MCP structured output. | One `ToolResult` envelope: `{data, source_status[], warnings[], next_cursor, truncated}` and one `ToolError` built from `ErrorCode` (keep errors.py's enum: INVALID_ARGUMENT, NOT_FOUND, AUTH_REQUIRED, RATE_LIMITED, UPSTREAM_TIMEOUT, ...). Return Pydantic models so FastMCP emits `outputSchema` and `structuredContent`. Raise only typed errors; a single tool decorator maps them. |
| ARCH-08 | high | API keys in query strings: GCP key :2840, PSE key :3223, SerpAPI :3207. Generic handlers echo `str(e)`: :2859 (`GCP docs search failed: {e}`), :3349 (`last_error = f"{p}: {e}"` returned as `details`). Verified that a `requests` ConnectionError message includes the full path and query string (`...url: /v1/x?key=...&q=a`) | Credentials can be returned to the MCP client and written to logs when an upstream times out or DNS fails. | Centralize auth injection in `HttpPort` (header where the API allows it) and run every error message and log line through a redactor that knows each `SourceSpec`'s secret names. Never put `str(exc)` in tool output; map to `ErrorCode` plus a safe message. |
| ARCH-09 | high | `query_papers` returns full chunk `content` and `max_results` is not clamped (:888-928); `get_paper_text` returns the whole paper (:931-949); `list_indexed_papers` returns everything (:953); `search_iam_index` unclamped (:3526); `analytics_sql`/`dataset_query` up to 10,000 rows (:3866). `Settings.max_response_bytes` (config.py:25) unused. `BaseAdapter.get_json` checks size after loading the whole body (adapters/base.py:112-114) | No response budget. Large results can blow the client context window, and memory caps on upstream payloads are cosmetic. | Response budgeter in the envelope layer (bytes and items) with `truncated` and cursor continuation; stream with `max_bytes` in `HttpPort`; constrain every numeric arg with `Annotated[int, Field(ge=1, le=N)]`. |
| ARCH-10 | high | `papers.arxiv_id` is the key for arXiv, `doi:` (:1993), `core:` (:2722) and `iam:<project>:<hash>` (:3484) rows; IAM rows store a URL in `pdf_path` (:3511). `index_all_papers` maps filenames with `stem.replace("_", "/")` (:846), so `doi_10.1145_x.pdf` (written at :1956) becomes `doi/10.1145/x` instead of `doi:10.1145/x`, and `core_123.pdf` becomes `core/123` | The identity model is overloaded and lossy. Re-scanning creates duplicate rows under wrong ids and triggers bogus arXiv metadata lookups. IAM crawl pages share the paper corpus, so they appear in `query_papers`, `list_indexed_papers`, `analytics_sql` and embeddings. | Use the `works / identifiers / documents / extractions / document_chunks` model already sketched in repository.py:186-243, with a canonical id service (`core/ids.py`) that normalizes DOI, arXiv, PMID, OpenAlex, CORE, NCT. Keep docs pages in a separate collection or `work_type`. Store a manifest, never parse ids from filenames. |
| ARCH-11 | medium | `_extract_main_text` collapses all whitespace to single spaces (:3372); `chunk_pages` only breaks at `\n` (:478-520). Verified: a 36,001-char page yields one 36,001-char chunk plus a 200-char tail duplicate. `tests/test_server.py::TestPaperIndexEdgeCases::test_very_long_content` (:1415) takes 126 s of the 132 s suite because FTS5 `snippet()` over a 500 KB chunk is pathological | Crawled IAM pages are never actually chunked, which defeats BM25 locality, slows snippets badly and silently truncates embeddings (bge-small reads 512 tokens). | Chunker that splits on paragraph, sentence, then hard character limits regardless of newlines; put a time budget on the long-content test and mark perf tests separately. |
| ARCH-12 | medium | Embeddings keyed by SQLite AUTOINCREMENT `chunk_id` (:4108). `upsert_paper` deletes and re-inserts chunks (:171) and `remove_paper` (:212) never touches `emb.embeddings`. `embedding_stats` computes `missing = total - embedded` (:4063). `content_hash` stored but never compared | Re-indexing or removing a paper orphans vectors; stats become wrong; the two stores (SQLite file, DuckDB file) have no shared transaction. | Library store owns chunk identity (content hash or `extraction_id:index`), and deletion cascades to vectors. Consider keeping vectors in the same SQLite file (sqlite-vec) or behind an `Embedder` + `VectorIndex` port in an optional extra. |
| ARCH-13 | medium | `logging.basicConfig` at import (:60). 17 env reads frozen into module constants at import (:46-51, :1611, :2016, :2502, :2757, :3050-3058, :3620, :3776, :3987-3991). Globals with no shutdown: `_index` :614, `_vertex_ai_creds` :3059, `_duckdb_conn` :3780, `_embed_model` :3993. Late imports with `noqa: E402` at :4191-4196. `FastMCP` instantiated at import (:612). Tests monkeypatch module globals (tests/test_server.py:1357) | Import-time side effects reconfigure host logging, make config untestable without monkeypatching, and prevent building two app instances (for example, tests with different settings). | Composition root `build_app(settings) -> FastMCP` with a lifespan context that creates and closes the HTTP client, stores and models. No work at import. Logging configured only in the CLI entry point and always to stderr. |
| ARCH-14 | medium | Two config systems with different variable names: server.py `ARXIV_DOWNLOAD_DIR`, `ARXIV_DB_PATH`, `DUCKDB_DATASETS_DIR`, `EMBED_DB_PATH` vs config.py:52-76 `RESEARCH_MCP_DATA_ROOT`, `RESEARCH_MCP_DATASET_ROOT`, `RESEARCH_MCP_HOST`, `RESEARCH_MCP_AUTH_TOKEN`. `int(os.environ[...])` at import (:50-51, :3988) crashes startup on bad input | Operators cannot know which variables matter. Validation (loopback binding, remote-mode feature locks, byte budgets) exists only in the unused Settings. | Single `Settings` (pydantic-settings) with nested per-source sections generated from `SourceSpec.auth` and `SourceSpec.config`. Add a `research-mcp doctor` command that prints which sources are configured, disabled or failing their health probe. |
| ARCH-15 | medium | `PaperIndex` opens SQLite with `check_same_thread=False` and never closes (:80-85). DuckDB `ATTACH` built with f-strings from paths (:3793, :4025), so a quote in a path breaks the SQL. `INSTALL sqlite; INSTALL vss` at runtime (:3791, :4031) downloads DuckDB extensions on first use. Legacy `papers/chunks` and repository.py `works/...` schemas both target the same DB; the one-shot `INSERT OR IGNORE` migration (repository.py:244-303) is never called | Resource lifecycle is implicit; analytics depends on network access to DuckDB's extension repo; two schemas would diverge if the migration ever ran while v1 kept writing. | Lifespan-managed stores; parameterize or validate attach paths; vendor or pre-install extensions, or drop DuckDB from the default install (ARCH-19). v2 owns one schema with numbered migrations; provide a one-way import from the v1 DB. |
| ARCH-16 | medium | Three unbounded PDF downloaders with no content-type or `%PDF-` check (:744-755, :1960-1971, :2692-2702) while `security.download_pdf_atomic` (security.py:225-326) is unused. `fetch_cloud_doc_page` checks the host then lets `requests` follow redirects anywhere (:2949). Crossref parsed in `_parse_crossref` (:1625) and again in `_check_one_doi` (:4261); DataCite parsed inline in `resolve_doi` (:1700-1724) and in adapters/datacite.py; HTML stripping regexes duplicated (:2963-2966, :3364-3371); OpenAlex reached both via raw requests and `_OpenAlexSignal(BaseAdapter)` (:4231); two Job models (models.py:161-186 and jobs.py:13-49) | Duplicated domain logic drifts; safety work done once is not used where it matters. | One `DocumentFetcher` port backed by the security.py downloader and egress policy; one parser per upstream living in that source's adapter; one Job model. |
| ARCH-17 | medium | `_clamp` applied on some tools only (:629); missing on `query_papers`, `search_iam_index`, `get_paper_metadata` (id count), `search_arxiv.start` and `sort_by`. `search_iam_index` reaches into `idx.conn` (:3547) and bypasses `PaperIndex.search` fallback: verified `search_iam_index("***")` raises `sqlite3.OperationalError: fts5: syntax error near ""`. 39 implicit-Optional params (`str = None`) | Inconsistent validation produces raw exceptions; tools bypass the persistence boundary. | Declare constraints in tool signatures (Pydantic `Annotated`, `Literal` for enums such as sort). Tools call services, services call stores; no SQL in tool modules. |
| ARCH-18 | medium | 321 test functions, 356 collected items: 354 pass, 2 module-level skips covering 13 tests that target nonexistent modules (tests/test_modern_mcp.py:14-28, tests/test_research_workflows.py:11-23). Mocks patch `server.requests.get` (implementation-coupled); payloads are inline dicts, no recorded fixtures. 36 of 53 tools are never called by name in tests. No MCP protocol test (list_tools, call_tool through a client). No live canary. `sys.path.insert` hack (tests/test_server.py:12) | Good news: suite is hermetic (verified: all pass with sockets and DNS blocked, 2.9 s excluding the slow test). Bad news: it cannot detect upstream API drift, does not exercise the tool contract, and refactoring the HTTP layer breaks every mock. | Per-adapter contract tests driven by recorded fixtures (`tests/sources/<name>/fixtures/*.json`): parse happy path, empty, 429, 5xx, malformed, oversize. A conformance test parametrized over the registry so every new adapter gets the same checks for free. In-memory MCP client tests for the tool surface and schemas. A nightly, opt-in live job that runs each `SourceSpec.health_probe` and records fresh fixtures. |
| ARCH-19 | medium | pyproject.toml:38 `my-research-mcp = "server:mcp.run"` bypasses argparse (:4601-4613), so `--transport/--port` are unavailable from the installed command; :50 `py-modules = ["server"]` installs a top-level module named `server` into site-packages. SSE transport only (Streamable HTTP is the current MCP HTTP transport). Version skew: pyproject 2.0.0, `research_mcp.__version__` 3.0.0, UAs 1.0 and 2.0. Mandatory heavy deps (pyproject.toml:21-28): pymupdf imported at top level (:35; AGPL-3.0 licensed while the project is MIT), duckdb, fastembed (onnxruntime plus a model download), google-auth used only for Vertex (:3062). Lower-bound pins only, no lock file | A search-only user must install PDF, analytics, embedding and Google auth stacks. The installed command differs from `python server.py`. A generic top-level `server` module collides with other packages. | `src/research_mcp/` layout, console script `research-mcp = research_mcp.cli:main`, single version source. Extras: `[pdf]`, `[analytics]`, `[embeddings]`, `[vertex]`; sources declare required extras in `SourceSpec` and report `unavailable` if missing. Lock with uv. Support stdio and Streamable HTTP. Review the PyMuPDF license choice (pypdf or pdfminer.six as a permissive default). |
| ARCH-20 | low | .github/workflows/ci.yml: one job, Python 3.10-3.12 (no 3.13), no pip cache, no coverage report or threshold, no type check, no wheel build or entry-point smoke test, actions pinned by tag. Ruff selects only E,F,I,W (pyproject.toml:58); widening finds 32 BLE001 blind excepts and C901 hot spots `download_paper_by_doi` (19), `_check_one_doi` (17), `search_iam_docs` (16). mypy finds 110 errors (99 in server.py: 43 assignment, 33 arg-type, 14 union-attr). Makefile `test-cov` covers `server` only | CI cannot catch typing regressions, complexity growth, packaging breakage or coverage loss. | CI: ruff (add B, UP, SIM, ASYNC, BLE, S, C90), mypy or pyright strict on `src/`, pytest with coverage gate per package, build wheel and run `research-mcp --help` plus an MCP `list_tools` smoke, matrix 3.11-3.13, uv cache, SHA-pinned actions, scheduled live-probe workflow. |
| ARCH-21 | low | Logger `arxiv-mcp` (:61), server `my-research`, env prefix `ARXIV_` for non-arXiv settings, generic ids in column `arxiv_id`. `search_iam_docs` docstring says Google PSE but code tries Vertex, Brave, SerpAPI first (:3237-3262). AGENTS.md and CLAUDE.md are copies of the same hand-maintained tool inventory | Naming leaks v0 history and misleads readers and the model. Tool docs drift from code. | Consistent `research_mcp` naming and `RESEARCH_MCP_` env prefix. Generate the tool and source inventory from the registry (`list_sources`, a `make docs` step) rather than maintaining it in two markdown files. |

### Things worth keeping (port, do not rewrite)

- FTS5 query sanitizer `PaperIndex.to_fts_query` and literal fallback (server.py:207-224, :383-427), well covered by tests.
- DSpace 8 query builder and error hints (:1212-1278), SHARE card parser and year filter (:2302-2363).
- Retraction status logic in `_check_one_doi` (:4261-4339), once split into a Crossref adapter plus an OpenAlex adapter.
- security.py (`validate_url`, `download_pdf_atomic`, `resolve_confined_path`) and its 12 tests.
- repository.py schema design and transaction helper; adapters/base.py cursor envelope (`encode_cursor`/`decode_cursor`).
- errors.py `ErrorCode` taxonomy.

---

## 3. Recommended v2 layout and ports

### 3.1 Layout

```
src/research_mcp/
  cli.py                  # entry point: stdio | streamable-http, logging to stderr, `doctor`
  app.py                  # build_app(settings) -> FastMCP; lifespan creates/closes ports
  settings.py             # one Settings; per-source sections derived from SourceSpec
  core/
    models.py             # WorkRecord, Identifier, SearchHit, Page, SourceStatus
    ids.py                # canonical id normalization (doi, arxiv, pmid, pmcid, openalex, core, nct)
    errors.py             # ErrorCode + ResearchError (from v1 errors.py)
    envelope.py           # ToolResult / ToolError, response budget, truncation
  http/
    client.py             # HttpPort impl on httpx.AsyncClient: retries, Retry-After, byte caps
    ratelimit.py          # async token bucket keyed by source
    redact.py             # secret scrubbing for errors and logs
    egress.py             # URL allowlist, redirect validation, PDF fetcher (from security.py)
  sources/
    base.py               # SourceAdapter protocol, SourceSpec, Capability enum
    registry.py           # discovery, enable/disable, health cache, extras check
    arxiv.py  semantic_scholar.py  openalex.py  crossref.py  datacite.py  unpaywall.py
    core_ac.py  dspace.py (one adapter, N instances)  osf_share.py  europe_pmc.py
    clinical_trials.py  opencitations.py  github.py
    docs_aws.py  docs_gcp.py  docs_mslearn.py
    websearch/            # IAM docs: provider strategies (vertex, brave, serpapi, google_pse)
  federation/
    service.py            # fan-out, deadline, cancellation, per-source status, merge
    dedupe.py             # identifier-based merge, provenance kept per source
    rank.py
  library/                # the one-off cache; optional extras
    store.py              # LibraryStore on SQLite (works/documents/chunks), migrations
    ingest.py             # fetch -> extract -> chunk -> index, as a job
    chunking.py
    extract_pdf.py        # [pdf] extra
    vectors.py            # [embeddings] extra
    analytics.py          # [analytics] extra (DuckDB), expert mode only
  jobs.py                 # one Job model, progress, cancellation
  tools/
    discovery.py          # search, get_record, list_sources, source_health
    scholarly.py          # get_citations, check_retractions, resolve_doi, cite
    docs.py               # search_docs (vendor + IAM), fetch_doc_page
    library.py            # save, query_library, get_text, remove, jobs
  prompts.py
tests/
  sources/<name>/fixtures/*.json + test_<name>.py   # recorded contract tests
  sources/test_conformance.py                       # parametrized over the registry
  federation/  library/  tools/ (in-memory MCP client)  live/ (opt-in, nightly)
```

Adding a source in v2 should mean: one file in `sources/`, one fixtures folder, an entry in the registry (or entry-point discovery), and nothing else. Tools, settings fields, `list_sources`, docs inventory and conformance tests pick it up automatically. Disabling a source is a settings flag or an automatic circuit breaker from failed health probes.

### 3.2 Key interfaces (ports)

```python
class Capability(StrEnum):
    SEARCH = "search"; GET = "get"; FULLTEXT = "fulltext"
    CITATIONS = "citations"; UPDATES = "updates"; DOCS = "docs"

@dataclass(frozen=True)
class SourceSpec:
    name: str                       # "openalex"
    title: str
    kinds: frozenset[str]           # {"scholarly"}, {"docs"}, {"code"}, {"trials"}
    capabilities: frozenset[Capability]
    id_schemes: frozenset[str]      # {"doi", "openalex"}
    auth: AuthSpec | None           # env var names, required/optional, header or query, docs URL
    rate: RateSpec                  # rps, burst, max_concurrency, daily quota
    timeout_s: float = 10.0
    max_page_size: int = 50
    polite_contact: bool = False    # inject mailto / UA contact
    extras: frozenset[str] = frozenset()   # {"vertex"} -> unavailable if not installed
    health_probe: ProbeSpec | None = None  # cheap query + expected shape
    enabled_by_default: bool = True

class SourceAdapter(Protocol):
    spec: ClassVar[SourceSpec]
    def __init__(self, http: HttpPort, settings: SourceSettings) -> None: ...
    async def search(self, req: SearchRequest) -> SearchPage: ...
    async def get(self, ident: Identifier) -> WorkRecord: ...          # if GET
    async def fulltext_candidates(self, w: WorkRecord) -> list[DocumentCandidate]: ...  # if FULLTEXT
    async def probe(self) -> HealthStatus: ...

class HttpPort(Protocol):
    async def get_json(self, url: str, *, source: str, params: Mapping[str, Any] | None = None,
                       headers: Mapping[str, str] | None = None, max_bytes: int | None = None) -> Any: ...
    async def post_json(self, url: str, *, source: str, json: Any, ...) -> Any: ...
    async def fetch_document(self, url: str, policy: DownloadPolicy) -> DownloadedDocument: ...

class FederatedSearch(Protocol):
    async def search(self, req: SearchRequest, *, sources: Sequence[str] | None,
                     kinds: Sequence[str] | None, deadline_s: float) -> FederatedResult: ...
# FederatedResult = items (deduped, provenance per source) + per_source:
#   {name: SourceStatus(state, latency_ms, count, next_cursor, error_code, retry_after_ms)}

class LibraryStore(Protocol):     # the cache; optional
    async def save_work(self, w: WorkRecord) -> str: ...
    async def add_extraction(self, document_id: str, chunks: Sequence[Chunk]) -> str: ...
    async def search_text(self, q: str, *, limit: int, scope: Scope) -> list[ChunkHit]: ...
    async def get_text(self, work_id: str, pages: PageRange | None) -> Page[Chunk]: ...
    async def remove(self, work_id: str) -> None: ...   # cascades to vectors

class TextExtractor(Protocol): def extract(self, path: Path) -> list[PageText]: ...
class Embedder(Protocol):      def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
class JobRunner(Protocol):     async def start(self, kind: str, fn: JobFn) -> Job: ...
```

Design rules for v2:
- Adapters are pure translation: request building and response normalization. No sleeping, retrying, logging of secrets or json.dumps in adapters.
- Federation never raises because one source failed; it reports status per source.
- Tool functions are thin: validate, call a service, wrap in the envelope.
- Everything slow or CPU-bound runs off the event loop.

---

## 4. Metrics

### 4.1 Lines of code

| Module | LOC | Used by running server |
|---|---:|---|
| server.py | 4,613 | yes (everything) |
| research_mcp/repository.py | 506 | no |
| research_mcp/security.py | 326 | no |
| research_mcp/models.py | 237 | partly (`SearchRequest`, adapter outputs) |
| research_mcp/adapters/base.py | 146 | yes |
| research_mcp/jobs.py | 121 | no |
| research_mcp/adapters/datacite.py | 98 | no |
| research_mcp/adapters/europe_pmc.py | 96 | yes |
| research_mcp/adapters/clinical_trials.py | 83 | yes |
| research_mcp/config.py | 77 | no |
| research_mcp/adapters/retractions.py | 71 | yes |
| research_mcp/errors.py | 64 | no |
| research_mcp/adapters/opencitations.py | 62 | yes |
| research_mcp/prompts.py | 61 | no (prompts never registered with FastMCP) |
| research_mcp/cache.py | 45 | no |
| research_mcp/__init__.py, adapters/__init__.py | 9 | n/a |
| **Production total** | **6,615** | about 5,170 lines live |
| tests/ (11 files) | 3,585 | |

Statements per coverage: server.py 1,749 statements.

### 4.2 Tools by area (53 total; 49 sync, 4 async)

| Area | Tools | Kind |
|---|---:|---|
| arXiv search/metadata | 2 | source |
| Semantic Scholar | 2 | source |
| DSpace (MIT, Harvard, Cornell, Penn) | 8 | source |
| DOI: resolve, Crossref search, citation | 3 | source |
| OpenAlex | 3 | source |
| OSF / PsyArXiv | 2 | source |
| Europe PMC, retractions, citations, trials | 4 | source (adapter-backed) |
| CORE search/get | 2 | source |
| Cloud docs (AWS, GCP, MS Learn, fetch) | 4 | source |
| IAM live web search | 1 | source |
| GitHub | 3 | source |
| **External source tools** | **34** | |
| Download + index (arXiv, DOI, CORE, index, index_all) | 5 | cache |
| Local FTS query + text | 2 | cache |
| Index management | 3 | cache |
| IAM crawl/index/list | 3 | cache |
| DuckDB analytics | 3 | cache |
| Embeddings | 3 | cache |
| **Local cache tools** | **19** | |

Distinct upstream hosts contacted: about 25. Upstreams with any rate limiting: 3 (arXiv, Semantic Scholar, CORE). Upstreams with retry: 1 (Semantic Scholar, 429 only).

### 4.3 Tests and coverage (measured)

- 321 test functions; 356 collected items; 354 passed, 2 module-level skips (13 tests against unimplemented modules).
- Runtime 132 s, of which 126 s is one test (`test_very_long_content`); 2.9 s without it.
- Hermetic: all tests pass with sockets and DNS blocked.
- Line coverage: total 62%; server.py 55%; research_mcp: models 98%, repository 90%, security 86%, adapters 66-87%, prompts 100%, cache/config/errors/jobs 0%.
- Tools never called by name in tests: 36 of 53.

server.py coverage by section:

| Section | Statements | Coverage |
|---|---:|---:|
| PaperIndex (SQLite FTS) | 134 | 99% |
| PDF extract/chunk | 50 | 98% |
| arXiv helpers | 38 | 100% |
| arXiv + index tools | 154 | 31% |
| Semantic Scholar | 50 | 16% |
| DSpace x4 | 141 | 94% |
| DOI / Crossref / Unpaywall | 142 | 30% |
| OpenAlex | 92 | 90% |
| OSF / PsyArXiv | 86 | 99% |
| CORE | 80 | 30% |
| Cloud docs | 76 | 37% |
| IAM docs | 270 | 18% |
| GitHub | 54 | 17% |
| DuckDB analytics | 83 | 23% |
| Embeddings | 87 | 15% |
| Adapter tools | 168 | 96% |
| Entry point | 11 | 9% |

### 4.4 Static analysis (measured)

- `ruff check .` with repo config (E,F,I,W): clean.
- Ruff extended (B, UP, SIM, ASYNC, S, BLE, C90): 743 findings, of which 655 are S101 asserts in tests; notable: 32 BLE001 blind except, 6 C901, 6 S608 SQL built with f-strings, 3 B905.
- mypy (ignore-missing-imports): 110 errors in 4 files (server.py 99, repository.py 8, datacite.py 2, security.py 1).
- Duplicated-pattern counts in server.py: 43 raw HTTP calls, 99 `json.dumps(..., indent=2)`, 61 `"error"` literals, 34 `except Exception`, 40 `raise_for_status()`, 17 module-level env reads, 4 `global` singletons.

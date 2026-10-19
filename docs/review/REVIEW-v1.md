# Research MCP v1: Deep Review (v1)

- **Date:** 2026-10-19
- **Subject:** `my-research-mcp-server` at commit `568d440` (`main`), the server in daily use
- **Method:** three independent review passes over a read-only copy of the code, plus read-only inspection of the live data folder on the owner's Mac and live probes of every upstream API. Tests, ruff, mypy and coverage were run on a scratch copy. No secret values were read or printed.
- **Detail:** [findings-architecture-v1.md](findings-architecture-v1.md) (ARCH-01 to ARCH-21), [findings-functional-v1.md](findings-functional-v1.md) (FUNC-01 to FUNC-40), [findings-operations-v1.md](findings-operations-v1.md) (OPS-01 to OPS-25)

This review replaces the earlier modernization spec and fix plans as the basis for v2. Those documents were about patching v1; this one asks what the tool should be.

## 1. What the owner wants from v2

These decisions were made during the review and shape every recommendation below.

| # | Decision |
|---|---|
| D1 | The value of the server is its **horizontal reach**: many sources, one server. Merge tools, not sources. Add sources where they are cheap to keep healthy. |
| D2 | Papers and documents are usually fetched for a **one-time need**. The local index is a working cache, not a library. |
| D3 | Cached items are kept **30 days**. Before an item expires the owner is **asked whether to archive or discard** it. Nothing is deleted without an answer. |
| D4 | The archive is the owner's **Google Drive**, through the locally synced folder (`My Drive/Research Archive/<year>/`). |
| D5 | v2 must be **maintainable and monitored**, and must **notify the owner when a credential is expiring or invalid** so it can be rotated. |
| D6 | v2 has a **lightweight local UI** to see sources, health, credentials, jobs and the cache. |
| D7 | The Google-based general web search (`search_iam_docs` through Programmable Search) is to be **decommissioned**. |
| D8 | "Penn" means UPenn ScholarlyCommons. |

## 2. Verdict

v1 reaches about 25 upstream services and has a hermetic test suite of 354 passing tests, so the core idea works. It is not a sound base for the next year of use:

1. **It is one 4,613-line module.** Every source, tool, parser and the storage layer live in `server.py`. Adding or fixing a source edits the monolith and four documentation files (ARCH-01, ARCH-04).
2. **A better foundation was written and never wired in.** `research_mcp/` contains a typed settings object, an SSRF-safe downloader, origin-scoped credentials, a versioned repository schema, a job service and an error taxonomy, about 1,300 lines with their own tests. `server.py` imports none of it, so every safety flag (`RESEARCH_MCP_AUTH_TOKEN`, expert SQL, crawler, custom paths) does nothing (ARCH-02, OPS-06, FUNC-36).
3. **Reach cannot be used as a whole.** There are 53 single-source tools, no federated search, no cross-source dedupe and no per-source health. Every tool blocks the event loop, so a fan-out is impossible as built (ARCH-03, ARCH-05, FUNC-01, FUNC-02).
4. **It has security holes that matter on a personal Mac.** SQL tools can read arbitrary local files, including the MCP client configs that hold every API key in plaintext (OPS-01, OPS-02, verified). The CORE key is sent to third-party PDF hosts (OPS-03). Google and SerpAPI keys travel in URLs and can be echoed into chat (OPS-04, ARCH-08).
5. **Three sources are degraded by upstream changes today,** and one is being shut down (section 4).
6. **Nothing is monitored.** There are no health checks, no quota visibility and no credential expiry detection (OPS-15).

Recommendation: **rebuild as v2 in a new repository**, porting the parts that are good (section 6), with the design in the [PRD](../prd/PRD-v1.md), [HLD](../design/HLD-v1.md) and [LLD](../design/LLD-v1.md).

## 3. Top findings

Severity follows the detailed files. Only the findings that drive v2 requirements are listed; every other finding is traced in the PRD components.

| # | Sev | Finding | Evidence | Drives |
|---|---|---|---|---|
| 1 | Critical | Arbitrary local file read through `analytics_sql` and a bypassable `dataset_query` sandbox (verified on DuckDB 1.5: `read_text`, list-form `read_csv`, `glob`). | OPS-01, OPS-02 | PRD-platform FR-PLAT-20 to 22 |
| 2 | Critical | Monolith plus an unwired foundation; two config systems; import-time side effects. | ARCH-01, ARCH-02, ARCH-13, ARCH-14 | HLD section 3, ADR 0004 |
| 3 | Critical | Every tool blocks the event loop (49 sync tools, sync HTTP under the 4 async ones). | ARCH-03, OPS-13 | ADR 0005 |
| 4 | Critical | Duplicate works: 54 PDFs have two rows each (versioned and unversioned arXiv id), so about 132 unique works sit behind 186 rows. Caused by inconsistent id handling in `download_paper` and `index_all_papers`. | FUNC-20, FUNC-21, ARCH-10 | PRD-search FR-SRCH-10 to 14 |
| 5 | High | No federated search, no cross-source dedupe, no per-source status. | FUNC-01, FUNC-02, ARCH-05 | PRD-search |
| 6 | High | No source abstraction: DSpace is 8 copy-paste tools; adding a source touches 5 places; no way to disable one. | ARCH-04, FUNC-12 | PRD-sources, ADR 0006 |
| 7 | High | Credential leaks: CORE bearer to third-party hosts; keys in URL query strings echoed via `str(e)`. | OPS-03, OPS-04, ARCH-08, FUNC-14 | PRD-platform FR-PLAT-10 to 16 |
| 8 | High | Downloads follow redirects anywhere, accept http and private IPs, have no size or PDF check, and the model can choose any path. | OPS-05, OPS-08, FUNC-15, FUNC-33 | PRD-cache FR-CACHE-01 to 06 |
| 9 | High | Fetch works for only 3 of about 25 sources (arXiv, Unpaywall/Semantic Scholar, CORE). | FUNC-08 | PRD-cache FR-CACHE-01 |
| 10 | High | No monitoring, no quota tracking, no credential expiry detection; undocumented endpoints fail silently as "0 results". | OPS-15, OPS-16 | PRD-health |
| 11 | High | Semantic search covers at most about 7% of chunks; vectors are orphaned on every re-index. | FUNC-29, FUNC-30, ARCH-12, OPS-17 | PRD-cache FR-CACHE-20 to 24 |
| 12 | High | Unbounded outputs (whole papers, 1,000-record Semantic Scholar pages, 10,000-row SQL results). | ARCH-09, FUNC-04, FUNC-16 | PRD-platform FR-PLAT-30 |
| 13 | High | Each MCP client starts its own process: rate limits break across clients, DuckDB file locks collide, no shared health. | OPS-12 | ADR 0002 |
| 14 | Medium | Web pages crawled into the papers table become one unbounded chunk each (a 36 KB page is one chunk; one test takes 126 of 132 seconds because of it). | FUNC-22, FUNC-23, ARCH-11 | PRD-cache FR-CACHE-12 |
| 15 | Medium | Tests: 36 of 53 tools are never called; mocks patch `server.requests.get` with inline payloads; nothing detects upstream drift. Coverage 62%. mypy reports 110 errors. | ARCH-18, ARCH-20 | TEST-PLAN sections 2 and 3 |

## 4. Upstream changes found by live probes (2026-10-19)

| Source | Change | Effect on v1 | v2 response |
|---|---|---|---|
| OpenAlex | Usage-priced budget per API key since February 2026; `mailto` no longer gives a pool. | Keyless calls return 429 "Insufficient budget". | `OPENALEX_API_KEY` from Keychain; budget tracked in source health. |
| Semantic Scholar | `/paper/search/bulk` ignores `limit` (3 requested, 1,000 returned). | Huge responses into the model's context. | Use `/paper/search`; bulk only in jobs; optional key. |
| Crossref | New rate tiers since 2025-12-01; without `mailto` a client is in the public pool (1 list request per second, concurrency 1). | Fan-out throttles. | Required contact email. |
| Google Programmable Search JSON API | Closed to new customers; shuts down 2027-01-01. | The IAM web search fallback dies. | Removed (D7). |
| Brave Search API | Free tier removed (February 2026); metered. | v1 can spend up to 3 billed calls per IAM query. | Removed with the IAM web search (open decision O1). |
| Vertex AI Search | Renamed (reported as "Agent Search"); not re-verified. | Unknown. | Removed with the IAM web search (O1). |
| AWS docs, Microsoft Learn | v1 uses undocumented site-search endpoints; both vendors now ship official, unauthenticated MCP servers (probed OK). | Fragile. | Use the official servers as upstream sources. |
| Google Developer Knowledge API | v1 is GA; v1 code uses `v1alpha`. | Works but on a preview path. | Move to `v1`; key in the `x-goog-api-key` header. |
| UPenn ScholarlyCommons | Runs DSpace 7.6, not 8. | Labels only. | DSpace version recorded per repository. |

## 5. The live data

Inspected read-only on the owner's Mac (`~/arxiv-papers`, 307 MB):

- `arxiv_index.db` (34 MB): 186 rows in `papers`, 11,403 chunks, `user_version` 0, nothing indexed since 2026-04-16.
- 123 PDFs on disk. No PDF is missing: 176 rows point at 122 distinct files (the 54 duplicate pairs), and 10 rows are web documentation pages (Open Policy Agent, Apache Syncope) whose `pdf_path` holds the source URL.
- `embeddings.duckdb` (1.3 MB), far smaller than full coverage would need.

Because of D2 and D3, v2 starts with an empty cache and offers an **optional** import of this folder with a merge report (see [PRD-migration](../prd/components/PRD-migration-v1.md)).

## 6. Keep, port, drop

| Keep and port (proven code) | Drop |
|---|---|
| FTS5 query sanitizer with literal fallback (`server.py:207-224`, `383-427`) | The 53-tool surface (replaced by 17 tools over a source registry) |
| DSpace query builder and error hints (`server.py:1212-1278`) | Free-form SQL over the filesystem (OPS-01) |
| SHARE/OSF parser and year filter (`server.py:2302-2363`) | `search_iam_docs` and its four providers (D7, O1) |
| Retraction status logic (`server.py:4261-4339`) | Caller-chosen download and index paths |
| `research_mcp/security.py` (safe downloader, confined paths, scoped credentials) and its tests | Persisted DuckDB HNSW index (corruption risk) |
| `research_mcp/repository.py` schema ideas (works, identifiers, documents) | The automatic legacy migration in `repository.py` (carries the id bugs forward) |
| Adapter cursor envelope and `ErrorCode` enum | Undocumented AWS and Microsoft Learn site-search endpoints |
| The five research prompts in `prompts.py` | SSE transport |

## 7. Open decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| O1 | Remove all IAM web-search providers (Brave, SerpAPI, Vertex) along with Google Programmable Search, or keep one metered provider. | Remove all. Cover IAM through IETF, NIST, vendor docs and an allowlisted docs-site fetcher. |
| O2 | Register free keys for OpenAlex and Semantic Scholar. | Yes; OpenAlex is unusable without one. |
| O3 | PDF parser: PyMuPDF (best extraction; AGPL, acceptable for personal, non-distributed use) or a permissive parser. | PyMuPDF, isolated in a worker process. |
| O4 | Keep any SQL or dataset query tool. | Not in the first release; revisit if `~/research-datasets` is still used. |
| O5 | Second notification channel besides macOS notifications (OpenClaw inbox or none). | OpenClaw inbox, through a configurable webhook. |
| O6 | Run the AWS and Microsoft Learn MCP servers through v2 as sources, or add them to clients separately. | Through v2, so they appear on the source board and in federated search. |

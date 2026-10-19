# Component PRD: Search and Identity (v1)

- **Parent:** [PRD v1](../PRD-v1.md), goals G1 and G2
- **Design:** [HLD](../../design/HLD-v1.md) section 5; [LLD](../../design/LLD-v1.md) sections 6 and 7
- **Review findings addressed:** FUNC-01, FUNC-02, FUNC-04, FUNC-17, FUNC-18, FUNC-20, FUNC-21, ARCH-05, ARCH-10

## 1. Purpose

One call should search many sources at once and return one clean list: each work once, with every source that knows it, plus an honest report of which sources answered.

## 2. Requirements

### 2.1 Federated search

| ID | Requirement | Priority |
|---|---|---|
| FR-SRCH-01 | The `search` tool takes a query, an optional source selection (`auto`, a list of source ids, or group names), filters (year range, work type, open access only, provider, repository), a total limit, a per-source limit and a cursor. | Must |
| FR-SRCH-02 | `auto` picks enabled, healthy sources from the groups that fit the filters (default groups: `scholarly`, `preprints`); the selection is reported in the result. | Must |
| FR-SRCH-03 | Sources are called concurrently. Each source has its own timeout; the whole search has a deadline (default 8 s). Sources still running at the deadline are cancelled and reported as `timeout`. | Must |
| FR-SRCH-04 | Every result carries `source_status[]` with one entry per selected source: state (`ok`, `empty`, `timeout`, `rate_limited`, `error`, `unconfigured`, `disabled`, `skipped_unhealthy`, `skipped_budget`), result count, latency, retry-after when known, and a classified error code. A failing source never fails the search. | Must |
| FR-SRCH-05 | Results are merged into works (section 2.2), ranked by reciprocal rank fusion across sources with a small boost for works found by more sources, and returned with `found_in[]`, best identifiers, open-access flag and cache state. | Must |
| FR-SRCH-06 | The result is bounded by the response budget (NFR-05). A single opaque cursor carries every source's own cursor so the next page continues each source where it stopped. | Must |
| FR-SRCH-07 | `detail="compact"` (default) returns title, authors (first three and a count), year, venue, identifiers, OA flag and a short abstract snippet; `detail="full"` adds full abstracts within the budget. | Must |
| FR-SRCH-08 | Sources in `rate_limited` or `down` state are skipped by `auto` until their cool-off ends, and reported as `skipped_unhealthy`. An explicit request for such a source tries it once. | Should |
| FR-SRCH-09 | Every search is recorded (query hash, sources, filters, statuses, timings) for telemetry and for the UI; query text is stored only when debug logging is on. | Should |

### 2.2 Identity and dedupe

| ID | Requirement | Priority |
|---|---|---|
| FR-SRCH-10 | Identifiers are normalized at the boundary: DOI lowercased without prefix or resolver URL; arXiv id without version (the version is kept separately), old-style ids in `archive/NNNNNNN` form; PMID and PMCID numeric forms; OpenAlex, Semantic Scholar, CORE, NCT, RFC, handle and DSpace UUID in canonical form; URLs normalized for scheme, host case and trailing slash. | Must |
| FR-SRCH-11 | A work is identified by any of its normalized identifiers; two records sharing any identifier are the same work. | Must |
| FR-SRCH-12 | Records with no shared identifier are merged when normalized title, year and first-author surname all match; merges by this rule are flagged `fuzzy` in the result. | Should |
| FR-SRCH-13 | Identity is never derived from a file name. | Must |
| FR-SRCH-14 | When merged records disagree (title, year, retraction status), the result notes the disagreement and the source of each value. | Should |

### 2.3 Work lookup

| ID | Requirement | Priority |
|---|---|---|
| FR-SRCH-15 | `get_work` accepts any identifier form (prefixed ids such as `doi:`, `arxiv:`, `pmid:`, bare DOIs, resolver URLs, arXiv URLs, DSpace handles) and returns one merged record from every source that can resolve it. | Must |
| FR-SRCH-16 | The record lists open-access locations from all sources (arXiv, PMC, repository bitstreams, Unpaywall, OpenAlex, CORE, OSF) with license and version where known. | Must |
| FR-SRCH-17 | The record includes integrity status (section 2.5) and cache state (cached, pinned, archived, discarded, none). | Must |

### 2.4 Citations, authors and export

| ID | Requirement | Priority |
|---|---|---|
| FR-SRCH-20 | `citations` returns citing and cited works for a work, merged from OpenCitations, OpenAlex and Semantic Scholar, deduplicated by DOI, with titles filled in, and paged. | Must |
| FR-SRCH-21 | `authors` searches authors across OpenAlex, ORCID and DBLP and returns merged author records with identifiers. | Should |
| FR-SRCH-22 | `cite` exports one or more works (or a collection) as BibTeX, CSL-JSON, RIS or formatted text in a named style. DOIs use content negotiation; other works use a stored CSL snapshot formatted locally. Unknown styles and formats are rejected, not silently replaced. | Must |
| FR-SRCH-23 | `cite` works for archived and discarded items from their stored metadata. | Must |

### 2.5 Integrity

| ID | Requirement | Priority |
|---|---|---|
| FR-SRCH-25 | `check_integrity` reports retractions, corrections and expressions of concern for given works from Crossref update relations (including Retraction Watch records) and OpenAlex. | Must |
| FR-SRCH-26 | `check_integrity("cache")` re-checks every cached and archived work; a work retracted since it was cached is flagged in the next cache review. | Should |

## 3. Out of scope

Relevance tuning beyond reciprocal rank fusion; full-text search across sources that do not offer it; Google Scholar.

## 4. Acceptance

Tests `AT-SRCH-*` in [TEST-PLAN v1](../../test-plan/TEST-PLAN-v1.md).

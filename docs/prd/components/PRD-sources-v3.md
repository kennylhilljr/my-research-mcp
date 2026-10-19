# Component PRD: Sources (v3)

- **Parent:** [PRD v4](../PRD-v4.md), goals G1 and G3; supersedes [v2](PRD-sources-v2.md)
- **Design:** [HLD v3](../../design/HLD-v3.md) section 4; [LLD v4](../../design/LLD-v4.md) sections 4, 5 and 5.5; ADRs [0006](../../adr/0006-source-adapter-contract.md) and [0012](../../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md)
- **Review findings addressed:** ARCH-04, ARCH-06, FUNC-03 to FUNC-12, OPS-15, OPS-16

## Changes from v2

Owner decision of 2026-10-19: three free reference sources from the owner's separate K-12 teacher server join the catalog as the `reference` group: Library of Congress (`loc`), Open Library (`open_library`) and Wikipedia (`wikipedia`), sources 43 to 45. The teacher server itself is not migrated or changed; its other sources stay there.

Earlier changes (v2, [ADR 0012](../../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md)): requirements are domain-neutral; every service v1 calls stays reachable (FR-SRC-17); site sets and the optional `web` group (FR-SRC-18 to FR-SRC-23); four web-search sources (39 to 42); `docs_site` instances are owner-configured, with v1's six crawl projects as defaults.

## 1. Purpose

Horizontal reach is the product, across any subject area. This component defines how a source is added, described, called, tested and switched off, and which sources v2 ships with.

## 2. Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-SRC-01 | Every source is described by a declarative `SourceSpec`: id, title, group, capabilities, identifier schemes it understands, auth (credential names, header or query placement, required or optional, signup URL), rate policy (requests per second, burst, concurrency, daily quota), timeout, maximum page size, contact-email requirement, optional dependency extras, health probe, default enabled flag, and status note (for example a shutdown date). | Must |
| FR-SRC-02 | Every source is implemented by one adapter module that satisfies the `SourceAdapter` contract: `search`, `get`, `fulltext_candidates`, `citations` (where supported) and `probe`. Unsupported capabilities are declared in the spec, not stubbed. | Must |
| FR-SRC-03 | Adapters only translate between the upstream API and the normalized models. They never sleep, retry, read secrets, write files, log request URLs with credentials, or import an HTTP library; all I/O goes through the shared `HttpPort`. | Must |
| FR-SRC-04 | A registry discovers adapters at startup, builds configured instances, and exposes them by id and by group. Two or more instances of one adapter (for example four DSpace repositories, several docs sites) are created from configuration alone. | Must |
| FR-SRC-05 | Any source can be disabled in configuration or from the UI without a code change. Disabled sources are never called, are listed with state `disabled`, and are skipped by federated search with that status. | Must |
| FR-SRC-06 | A source whose required credential is missing is listed as `unconfigured` with the exact fix (Keychain item name and signup URL) and is skipped by federated search. | Must |
| FR-SRC-07 | A source whose optional dependency extra is not installed is listed as `unconfigured` with the install command. | Should |
| FR-SRC-08 | Every adapter ships seven recorded fixtures: a normal search result, an empty result, a normal get result, HTTP 429 with `Retry-After`, HTTP 5xx, a malformed body, and an oversize marker. A conformance suite parametrized over the registry runs the same checks against every adapter. | Must |
| FR-SRC-09 | Every adapter maps upstream records to the normalized `WorkRecord` with provenance (source id, upstream id, adapter version, retrieval time) and normalized identifiers. | Must |
| FR-SRC-10 | Upstream MCP servers (AWS Knowledge, Microsoft Learn) are supported as a source kind: the adapter calls the upstream server through a platform MCP client port built on the shared HTTP client, so rate limits, host policy, telemetry and redaction still apply, and maps its results. | Should |
| FR-SRC-11 | Sources that ask for a contact email or a descriptive user agent (Crossref, Unpaywall, arXiv, OpenAlex) receive the configured owner contact; the server refuses to start an affected source with a placeholder address (no `example.com`). | Must |
| FR-SRC-12 | An opt-in live check (`research-mcp sources check --live`) calls each enabled source once and can refresh its fixtures for review. | Should |
| FR-SRC-13 | The source inventory (`docs/generated/sources.md`, linked from the README and agent instructions) is generated from the registry (`research-mcp sources --markdown`); CI fails if the committed inventory is stale. | Must |
| FR-SRC-14 | Sources with an announced shutdown carry the date in their spec and show `deprecated(days)` until removed. | Should |
| FR-SRC-15 | Docs-site sources fetch and crawl only hosts and path prefixes on their allowlist, honor `robots.txt`, and match filters on the parsed host and path, never on a substring of the URL. | Must |
| FR-SRC-16 | Adding a new source requires only: one adapter module (discovered automatically), one fixtures folder, and its acceptance tests; the generated inventory is refreshed. The new-source checklist in LLD section 5.4 is the definition of done. | Must |
| FR-SRC-17 | Every upstream service v1 calls stays reachable through a v2 source (the mapping is in the migration tool map). The one substitution: v1's undocumented AWS and Microsoft Learn site-search endpoints are replaced by those vendors' official MCP servers, which cover the same documentation. v1's docs-domain list and crawl projects ship in the default configuration as editable data, not code. | Must |
| FR-SRC-18 | Named **site sets** (a name and a list of domains) are configuration. The default configuration holds v1's docs-domain list as the site set `v1_docs`. The owner can add, edit or remove site sets in the config file (or with `research-mcp config set`) without a code change; the UI settings page shows them. | Must |
| FR-SRC-19 | The `web` group holds the optional web-search sources: `vertex_search` (one instance per Vertex AI Search engine, `vertex_<name>`), `brave_search`, `serpapi` and `google_pse`. Each is disabled until its settings and credential are present, is never in the default fan-out, and runs only when a caller names the group or the source. | Must |
| FR-SRC-20 | Each web-search source has a daily call cap (default 100, owner-set). At the cap the source reports `budget_exhausted` until the next local midnight, and federated search skips it with that status. | Must |
| FR-SRC-21 | Within the `web` group, the strategy is `fallback` by default: call the configured sources in order (default order: Vertex, Brave, SerpAPI, Programmable Search) and stop at the first that returns results without error. `all` calls every configured web source and merges the results. The order and strategy are settings. | Must |
| FR-SRC-22 | `search` accepts an optional `site_set`. Brave, SerpAPI and Programmable Search restrict results to that set's domains (splitting the domain list into several queries when a provider limits query length, as v1 does for Brave); a Vertex engine's scope is set in Google Cloud, so `site_set` filters its results after the call. An unknown set name is `invalid_argument`. | Must |
| FR-SRC-23 | `vertex_search` authenticates with the owner's Google sign-in (Application Default Credentials) through the optional `gcp` extra; its own code never opens or copies the credential file (the `google-auth` library reads it), keeps the access token in memory only, and sends it only to `discoveryengine.googleapis.com`. Project, location and engine id are settings, not secrets. | Must |

## 3. Source catalog

Groups help federated search pick defaults (for example `scholarly` and `preprints` for a literature question). "Auth" names Keychain items (`research-mcp/<NAME>`). "M" is the milestone that delivers the adapter.

| # | Source id | Group | Capabilities | Auth | Notes | M |
|---|---|---|---|---|---|---|
| 1 | `arxiv` | preprints | search, get, fulltext | none | https only; 1 request per 3 s across all clients | M0 |
| 2 | `crossref` | scholarly | search, get, updates | contact email | polite pool needs `mailto` | M0 |
| 3 | `openalex` | scholarly | search, get, fulltext, citations, authors | `OPENALEX_API_KEY` | usage budget; use `topics`, `last_known_institutions`; page size 100 | M0 |
| 4 | `semantic_scholar` | scholarly | search, get, citations | `SEMANTIC_SCHOLAR_API_KEY` (optional) | `/paper/search` for interactive; bulk only in jobs | M1 |
| 5 | `datacite` | scholarly | search, get | none | port the existing adapter | M1 |
| 6 | `core` | scholarly | search, get, fulltext | `CORE_API_KEY` | key never sent to non-CORE hosts | M1 |
| 7 | `unpaywall` | scholarly | fulltext (OA locator) | contact email | no placeholder email | M1 |
| 8 | `openaire` | scholarly | search, get | none | EU aggregator | M1 |
| 9 | `doaj` | scholarly | search | none | OA journals | M1 |
| 10 | `zenodo` | scholarly | search, get, fulltext | `ZENODO_TOKEN` (optional) | datasets, software, reports | M1 |
| 11 | `hal` | scholarly | search, get, fulltext | none | French OA archive | M1 |
| 12 | `dblp` | scholarly | search | none | bot protection from datacenter IPs; fine from the Mac | M1 |
| 13 | `orcid` | scholarly | authors | none | author identity | M1 |
| 14 | `ads` | scholarly | search, get, citations | `ADS_API_TOKEN` | disabled by default | M1 |
| 15 | `lens` | scholarly | search | `LENS_API_TOKEN` | patents; disabled by default | M1 |
| 16 | `osf` | preprints | search, get, fulltext | none | providers as a filter (PsyArXiv, SocArXiv) | M1 |
| 17 | `biorxiv` | preprints | get, fulltext | none | discovery through Europe PMC and Crossref | M1 |
| 18 | `medrxiv` | preprints | get, fulltext | none | as above | M1 |
| 19 | `ssrn` | preprints | search, get | none | through Crossref prefix 10.2139; PDFs often need login | M1 |
| 20 | `hf_papers` | preprints | search | none | ML papers with code; cap response size | M1 |
| 21 | `europe_pmc` | biomed | search, get, fulltext | none | port the existing adapter; add PMC OA full text | M1 |
| 22 | `pubmed` | biomed | search, get | `NCBI_API_KEY` (optional) | E-utilities | M1 |
| 23 | `clinical_trials` | biomed | search, get | none | port the existing adapter | M1 |
| 24 | `dspace_mit` | repositories | search, get, fulltext | none | DSpace adapter instance; version recorded | M1 |
| 25 | `dspace_harvard` | repositories | search, get, fulltext | none | instance | M1 |
| 26 | `dspace_cornell` | repositories | search, get, fulltext | none | instance | M1 |
| 27 | `dspace_penn` | repositories | search, get, fulltext | none | UPenn ScholarlyCommons; DSpace 7.6 | M1 |
| 28 | `ietf` | standards | search, get, fulltext | none | Datatracker and RFC Editor; status and obsoletes | M1 |
| 29 | `nist` | standards | search, get, fulltext | none | Crossref prefix 10.6028 plus CSRC pages | M1 |
| 30 | `nvd` | standards | search, get | `NVD_API_KEY` (optional) | CVE API 2.0 | M1 |
| 31 | `aws_knowledge` | vendor_docs | search, get | none | official AWS Knowledge MCP server (upstream MCP) | M1 |
| 32 | `ms_learn` | vendor_docs | search, get | none | official Microsoft Learn MCP server (upstream MCP) | M1 |
| 33 | `google_devknowledge` | vendor_docs | search, get | `GOOGLE_DEVKNOWLEDGE_API_KEY` | v1 API; key in `x-goog-api-key` header | M1 |
| 34 | `docs_site` | vendor_docs | search (local), get, crawl | none | owner-configured instances (`docs_site_<name>`), each with an allowlist; v1's six crawl projects ship as defaults | M1 |
| 35 | `github` | code | search, get | `GITHUB_TOKEN` | repos, code (needs token), README | M1 |
| 36 | `opencitations` | integrity | citations | `OPENCITATIONS_TOKEN` (optional) | port the existing adapter | M1 |
| 37 | `crossref_updates` | integrity | updates | contact email | retractions and corrections, including Retraction Watch records | M1 |
| 38 | `eric` | education | search, get | none | education research | M1 |
| 39 | `vertex_search` | web | search | Google sign-in (Application Default Credentials); `gcp` extra | instances `vertex_<name>` with project, location, engine id; metered, capped; first in the fallback order | M1 |
| 40 | `brave_search` | web | search | `BRAVE_SEARCH_API_KEY` | key in the `X-Subscription-Token` header; metered, capped; long site sets split into batches | M1 |
| 41 | `serpapi` | web | search | `SERPAPI_API_KEY` | key accepted only as a query parameter (URL never logged); metered, capped | M1 |
| 42 | `google_pse` | web | search | `GOOGLE_DEVKNOWLEDGE_API_KEY` (shared with source 33, as in v1) | engine id in settings; key in the `x-goog-api-key` header; shutdown announced for 2027-01-01, shown as `deprecated(days)` | M1 |
| 43 | `loc` | reference | search, get, fulltext | none | Library of Congress JSON API (`fo=json`): photos, manuscripts, maps, books, newspapers; rate from LoC's published per-endpoint limits | M1 |
| 44 | `open_library` | reference | search, get | none | books and editions by title, author, subject or ISBN; metadata and cover links only, no lending | M1 |
| 45 | `wikipedia` | reference | search, get, fulltext | none | English Wikipedia search and summaries; full article text through `fetch` and `read`; descriptive user agent with the owner contact, as Wikimedia asks | M1 |

### 3.1 Changed from v1

v1's single web-search tool and its four providers become the four `web` sources above (FR-SRC-19 to FR-SRC-22). Nothing it called is removed.

### 3.2 Removed from v1

| v1 tool or source | Reason |
|---|---|
| Undocumented AWS docs and Microsoft Learn site-search endpoints | Replaced by the vendors' official MCP servers (sources 31 and 32), which cover the same documentation. This is the only substitution under FR-SRC-17. |
| Separate PsyArXiv tool | Becomes an OSF provider filter. |

## 4. Acceptance

Acceptance tests are in [TEST-PLAN v3](../../test-plan/TEST-PLAN-v3.md) under the `AT-SRC` prefix. Each source in section 3 has at least the six conformance fixtures (FR-SRC-08) and one probe test.

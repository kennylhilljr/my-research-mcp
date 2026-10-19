# Component PRD: Sources (v1)

- **Parent:** [PRD v1](../PRD-v1.md), goals G1 and G3
- **Design:** [HLD](../../design/HLD-v1.md) section 4; [LLD](../../design/LLD-v1.md) sections 4 and 5; [ADR 0006](../../adr/0006-source-adapter-contract.md)
- **Review findings addressed:** ARCH-04, ARCH-06, FUNC-03 to FUNC-12, OPS-15, OPS-16

## 1. Purpose

Horizontal reach is the product. This component defines how a source is added, described, called, tested and switched off, and which sources v2 ships with.

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
| FR-SRC-17 | No general web-search provider (Google Programmable Search, Vertex AI Search, Brave, SerpAPI) is registered, and their credentials are not imported (owner decision D7; open decision O1 covers the paid ones). | Must |

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
| 34 | `docs_site` | vendor_docs | search (local), get, crawl | none | allowlisted instances: Keycloak, Ory, OPA, Vault, Syncope, FreeIPA, OpenID, W3C | M1 |
| 35 | `github` | code | search, get | `GITHUB_TOKEN` | repos, code (needs token), README | M1 |
| 36 | `opencitations` | integrity | citations | `OPENCITATIONS_TOKEN` (optional) | port the existing adapter | M1 |
| 37 | `crossref_updates` | integrity | updates | contact email | retractions and corrections, including Retraction Watch records | M1 |
| 38 | `eric` | education | search, get | none | education research | M1 |

### 3.1 Removed from v1

| v1 tool or source | Reason |
|---|---|
| `search_iam_docs` with Google Programmable Search, Vertex AI Search, Brave and SerpAPI | Owner decision D7; Programmable Search shuts down 2027-01-01, Brave and SerpAPI are metered, Vertex was renamed. Open decision O1 confirms removing all four. |
| Undocumented AWS docs and Microsoft Learn site-search endpoints | Replaced by the vendors' official MCP servers (sources 31 and 32). |
| Separate PsyArXiv tool | Becomes an OSF provider filter. |

## 4. Acceptance

Acceptance tests are in [TEST-PLAN v1](../../test-plan/TEST-PLAN-v1.md) under the `AT-SRC` prefix. Each source in section 3 has at least the six conformance fixtures (FR-SRC-08) and one probe test.

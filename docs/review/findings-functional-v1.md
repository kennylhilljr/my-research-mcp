# my-research MCP server: functional review for v2 (tools, sources, data)

Reviewer scope: tools, external sources, data model. Code reviewed: read-only copy at `/home/claude/review/v1` (`server.py` 4,613 lines, 53 `@mcp.tool` functions; `research_mcp/`). Live API checks were run from this review sandbox on 2026-10-19 (a shared datacenter IP, which matters for the OpenAlex and DBLP results). Secrets: none printed; env var names only.

## 0. Owner direction that shapes this review

1. **Breadth first.** The owner values horizontal reach most: many sources, searched and retrieved in one place. v2 should merge *tools*, not *sources*, and add a federated search with per-source status and cross-source dedupe.
2. **Discovery and on-demand retrieval are the core** (search, fetch, read, cite). The local index is a *working cache*, not a curated library.
3. **Retention:** cached items live 30 days. Before expiry the owner is asked, per item, to archive (save) or discard. Nothing is deleted silently. Archived and discarded items keep metadata and a citation so they can be re-fetched.
4. **Legacy corpus:** an optional import plus a report, not a heavy zero-loss migration. The dedupe and id normalization findings still apply to that import.
5. `search_iam_docs` (Google Programmable Search and its Vertex, Brave, SerpAPI fallbacks) is being decommissioned. "Penn" means UPenn ScholarlyCommons.

## 1. Headline findings (summary)

| # | Finding |
|---|---|
| 1 | Reach is good (about 25 distinct upstream services), but it is spread across 53 single-source tools, with no federated search, no cross-source dedupe, and no per-source health. The best structural win is one `search` tool that fans out over a source registry. |
| 2 | Three sources are degraded today by upstream policy changes the code does not handle: **OpenAlex** now runs on a per-key daily budget (keyless calls returned 429 "Insufficient budget"); **Semantic Scholar** search uses the `/search/bulk` endpoint, which ignores `limit` (a `limit=3` call returned 1,000 records); **Crossref** calls carry no `mailto`, so they land in the public pool (1 list request per second, concurrency 1). |
| 3 | Retrieval (fetch) works for only 3 of about 20 sources (arXiv, DOI via Unpaywall or Semantic Scholar, CORE). DSpace, OSF/PsyArXiv, Europe PMC/PMC, OpenAlex OA links and GitHub can be found but not fetched into the cache. |
| 4 | The live index holds duplicate works: 54 PDFs are referenced by two rows each (one versioned id with a title, one unversioned id with an empty title). The code path that causes it is identified (FUNC-20). |
| 5 | A normalized, versioned repository (`research_mcp/repository.py`) plus config, security, jobs, cache, errors and prompts modules exist and are tested, but `server.py` imports none of them. v2 should build on them, not on `PaperIndex`. |
| 6 | Semantic search covers at most about 7% of chunks (1.3 MB `embeddings.duckdb` against roughly 17.5 MB needed for 11,403 x 384 float32 vectors), and re-indexing orphans embeddings. |

## 2. Tool inventory (v1, 53 tools)

Columns: **Writes** = writes the SQLite index, PDFs on disk, or the embeddings DB. **Output** = size behavior of the JSON returned (all tools use `json.dumps(..., indent=2)`, which adds roughly 20 to 30% whitespace).

### 2.1 arXiv, download, local index, management (10)

| Tool (line) | Purpose | Source / base URL | Auth env var | Writes | Output size |
|---|---|---|---|---|---|
| `search_arxiv` (654) | arXiv metadata search | `http://export.arxiv.org/api/query` (301 to https) | none | no | bounded, max 100 entries with abstracts |
| `get_paper_metadata` (699) | arXiv metadata by id list | same | none | no | bounded by id count (unvalidated) |
| `download_paper` (717) | Download arXiv PDF, auto-index | `https://arxiv.org/pdf` | none | PDF, index | small |
| `index_paper` (777) | Index one local PDF under any id | arXiv API for metadata | none | index | small |
| `index_all_papers` (829) | Scan download dir, index new or changed PDFs | arXiv API per file | none | index | **unbounded** `details` list |
| `query_papers` (888) | FTS5 BM25 over chunks | local SQLite | none | no | about 35 to 45 KB at default 20 hits (full 1,500-char chunk plus snippet each) |
| `get_paper_text` (931) | Full text or page range | local | none | no | **unbounded** (a 313-page thesis returns megabytes) |
| `list_indexed_papers` (953) | All rows plus stats | local | none | no | **unbounded** (186 rows today) |
| `remove_paper` (966) | Delete rows (keeps PDF) | local | none | index | small |
| `index_stats` (981) | Counts | local | none | no | small |

### 2.2 Scholarly metadata and discovery (14)

| Tool (line) | Purpose | Source / base URL | Auth env var | Writes | Output size |
|---|---|---|---|---|---|
| `search_semantic_scholar` (1013) | Cross-publisher search | `https://api.semanticscholar.org/graph/v1/paper/search/bulk` | none supported (no key header) | no | **unbounded: up to 1,000 records**, `limit` ignored by the endpoint |
| `get_semantic_scholar_paper` (1087) | Paper detail plus 20 refs and cites | `.../graph/v1/paper/{id}` | none | no | bounded |
| `resolve_doi` (1666) | DOI metadata, Crossref then DataCite | `https://api.crossref.org/works`, `https://api.datacite.org/dois` | none | no | small |
| `search_crossref` (1731) | Crossref search | `https://api.crossref.org/works` | none (no `mailto`) | no | max 100 with abstracts |
| `get_doi_citation` (1790) | Formatted citation, BibTeX, CSL-JSON | `https://doi.org/` content negotiation | none | no | small |
| `download_paper_by_doi` (1839) | Find OA PDF (Unpaywall, then S2), download, index | Unpaywall `https://api.unpaywall.org/v2`, S2 | `UNPAYWALL_EMAIL` | PDF, index | small |
| `search_openalex` (2103) | OpenAlex works search | `https://api.openalex.org/works` | `OPENALEX_EMAIL` (mailto only; no key) | no | max 200 with abstracts |
| `get_openalex_work` (2180) | Work detail, 30 refs, 20 related | `.../works/{id}` | same | no | bounded |
| `search_openalex_authors` (2223) | Author search | `.../authors` | same | no | max 50 |
| `search_osf` (2407) | OSF preprints, registrations, projects | `https://share.osf.io/api/v3/index-card-search` | none | no | max 100 |
| `search_psyarxiv` (2456) | PsyArXiv preset of the above | same | none | no | max 100 |
| `search_core` (2551) | CORE aggregator search | `https://api.core.ac.uk/v3` | `CORE_API_KEY` (required) | no | max 100 |
| `get_core_work` (2625) | CORE work detail | same | `CORE_API_KEY` | no | small |
| `download_core_paper` (2646) | Download CORE PDF, index | CORE download URL | `CORE_API_KEY` | PDF, index | small |

### 2.3 Institutional repositories, DSpace REST (8)

| Tool (line) | Purpose | Base URL | Auth | Writes | Output |
|---|---|---|---|---|---|
| `search_mit_dspace` (1434), `get_mit_dspace_item` (1475) | MIT search, item plus bitstream list | `https://dspace.mit.edu/server/api` | none | no | max 100 |
| `search_harvard_dash` (1493), `get_harvard_dash_item` (1518) | Harvard DASH | `https://dash.harvard.edu/server/api` | none | no | max 100 |
| `search_cornell_ecommons` (1531), `get_cornell_ecommons_item` (1556) | Cornell eCommons | `https://ecommons.cornell.edu/server/api` | none | no | max 100 |
| `search_penn_scholarly` (1569), `get_penn_scholarly_item` (1594) | UPenn ScholarlyCommons | `https://repository.upenn.edu/server/api` | none | no | max 100 |

All eight are thin wrappers over `_dspace8_search` / `_dspace8_get_item` (`server.py:1311`, `1364`). None can download a bitstream into the cache.

### 2.4 Biomedical, integrity, citation graph (4, via `research_mcp/adapters`)

| Tool (line) | Purpose | Base URL | Auth | Writes | Output |
|---|---|---|---|---|---|
| `search_europe_pmc` (4343) | PubMed, PMC, preprints, MeSH | `https://www.ebi.ac.uk/europepmc/webservices/rest` | none | no | max 50, cursor paging |
| `check_retractions` (4396) | Crossref update relations plus OpenAlex `is_retracted` | Crossref works, OpenAlex | none | no | max 25 DOIs |
| `get_citations` (4455) | Citing and cited DOIs | `https://api.opencitations.net/index/v2` | none | no | max 50 per direction, page param |
| `search_clinical_trials` (4524) | ClinicalTrials.gov v2 | `https://clinicaltrials.gov/api/v2/studies` | none | no | max 50, cursor |

### 2.5 Vendor docs, IAM docs, GitHub (11)

| Tool (line) | Purpose | Base URL | Auth | Writes | Output |
|---|---|---|---|---|---|
| `search_aws_docs` (2764) | AWS docs search | `https://proxy.search.docs.aws.com/search` (undocumented site proxy) | none | no | max 50 |
| `search_gcp_docs` (2819) | GCP docs via Developer Knowledge API | `https://developerknowledge.googleapis.com/v1alpha` | `GOOGLE_DEVKNOWLEDGE_API_KEY` | no | max 20 |
| `search_microsoft_docs` (2880) | Microsoft Learn search | `https://learn.microsoft.com/api/search` (undocumented site API) | none | no | max 50 |
| `fetch_cloud_doc_page` (2924) | Fetch and strip a docs page (3 allowed hosts) | page URL | none | no | capped by `max_chars` (default 20,000; caller can raise without limit) |
| `search_iam_docs` (3237) | Web search over 26 IAM doc domains; providers Vertex, Brave, SerpAPI, Google PSE | `discoveryengine.googleapis.com/v1`, `api.search.brave.com/res/v1/web/search`, `serpapi.com/search.json`, `www.googleapis.com/customsearch/v1` | `VERTEX_AI_PROJECT`, `VERTEX_AI_LOCATION`, `VERTEX_AI_IAM_ENGINE_ID`, `BRAVE_SEARCH_API_KEY`, `SERPAPI_API_KEY`, `GOOGLE_PSE_CX`, `GOOGLE_DEVKNOWLEDGE_API_KEY`, `IAM_DOCS_SEARCH_PROVIDER` | no | max 10. **To be decommissioned.** |
| `index_iam_project` (3442) | Crawl 6 IAM doc sites into the paper index | project sitemaps or seed URLs | none | index | small |
| `search_iam_index` (3526) | FTS over `iam:*` rows | local | none | no | max `max_results` (unclamped) |
| `list_iam_indexed` (3579) | Crawl targets and page counts | local | none | no | small |
| `search_github_repos` (3635) | Repo search | `https://api.github.com/search/repositories` | `GITHUB_TOKEN` (optional) | no | max 50 |
| `search_github_code` (3685) | Code search | `https://api.github.com/search/code` | `GITHUB_TOKEN` (required) | no | max 30 |
| `fetch_github_readme` (3736) | README text | `https://api.github.com/repos/{repo}/readme` | `GITHUB_TOKEN` (optional) | no | capped by `max_chars` (raisable) |

### 2.6 Analytics and embeddings (6)

| Tool (line) | Purpose | Backend | Auth / config | Writes | Output |
|---|---|---|---|---|---|
| `analytics_sql` (3835) | Read-only SQL over the SQLite index via DuckDB | DuckDB in-memory, SQLite attached | `ARXIV_DB_PATH` | no | up to 10,000 rows |
| `list_datasets` (3877) | List data files | filesystem | `DUCKDB_DATASETS_DIR` | no | unbounded file list |
| `dataset_query` (3913) | SQL over Parquet, CSV, JSON | DuckDB | `DUCKDB_DATASETS_DIR` | no | up to 10,000 rows |
| `embedding_stats` (4048) | Embedded vs total chunks | DuckDB `embeddings.duckdb` | `EMBED_DB_PATH`, `EMBED_MODEL_NAME`, `EMBED_DIM` | creates schema | small |
| `embed_chunks` (4070) | Embed missing chunks (local ONNX) | fastembed `BAAI/bge-small-en-v1.5` | same | embeddings | small |
| `semantic_search` (4124) | Cosine search over embedded chunks | DuckDB VSS | same | creates schema | max 100, 600-char snippets |

Other configuration env vars: `ARXIV_DOWNLOAD_DIR`, `ARXIV_DB_PATH`, `ARXIV_CHUNK_SIZE`, `ARXIV_CHUNK_OVERLAP`. Defined but unused by `server.py`: all `RESEARCH_MCP_*` variables in `research_mcp/config.py`.

## 3. Source status (checked 2026-10-19)

"Live" is the HTTP result of an anonymous request from the review sandbox. Cost tier: **Free** (no key), **Free-key** (free registration), **Metered** (free allowance then paid), **Paid**. Upkeep is the cost of keeping the source healthy: key management, quota, and fragility (how likely it is to break without notice).

| Source | v1 tools | Live check | Current API facts that matter | Auth (env var) | Tier | Upkeep | v2 recommendation |
|---|---|---|---|---|---|---|---|
| arXiv API | `search_arxiv`, `get_paper_metadata`, `download_paper`, indexing | `http://` returns 301 to `https://`; `https://export.arxiv.org/api/query` 200 | ToU: at most 1 request per 3 s, one connection, summed across all machines; metadata CC0; may store e-prints for personal research use but not re-serve them | none | Free | Low key cost; strict rate; stable | Keep. Switch base to https (`server.py:42`). Use a single global limiter shared by search, metadata and every indexing path. |
| Semantic Scholar Graph API | `search_semantic_scholar`, `get_semantic_scholar_paper`, DOI fallback | `/paper/search/bulk?limit=3` returned 1,000 records (168 KB, titles only); `/paper/search` returned 429 | Keyless traffic shares one throttled pool and is often 429 under load; key users start at 1 RPS. `search/bulk` has no `limit`; pages by `token`, up to 1,000 per call, not relevance ranked | add `SEMANTIC_SCHOLAR_API_KEY` (header `x-api-key`) | Free-key | Medium: frequent 429 without a key | Keep. Use `/paper/search` (relevance, `limit`/`offset`) for interactive search; use bulk only in jobs. Add key support and 429 backoff honoring `Retry-After`. |
| OpenAlex | `search_openalex`, `get_openalex_work`, `search_openalex_authors`, `check_retractions` | 429: "Insufficient budget. This request has no API key, so it counts against the free daily budget shared by everyone on your network's IP address" | Usage-priced budget model. Keyless: about one tenth of a free key's budget, shared per IP. Free key: $1/day budget, 30 req/s; keyless 10 req/s. Key via `api_key` param or `Authorization: Bearer`. `per_page` max 100 (code allows 200). The docs no longer mention `mailto`/polite pool. Known field deprecations: `concepts` (use `topics`), `last_known_institution` (use `last_known_institutions`) | add `OPENALEX_API_KEY`; `OPENALEX_EMAIL` alone is no longer enough | Metered (free key) | Medium: daily budget can run out; field churn | Keep (central to dedupe and OA links). Required key; per-call budget accounting; fix `per-page` clamp (`server.py:2136`), `concepts` filter (`2147`), `last_known_institution` (`2254`). |
| Crossref REST | `resolve_doi`, `search_crossref`, `download_paper_by_doi`, `check_retractions` | 200; anonymous response headers `x-api-pool: public-array`, `x-rate-limit-limit: 1`, `x-concurrency-limit: 1`; with `mailto` param: `polite-array`, limit 3, concurrency 3 | Since 2025-12-01: public pool 5 req/s single record, 1 req/s lists, concurrency 1; polite pool (add `mailto`) 10 req/s single, 3 req/s lists, concurrency 3 | add `CROSSREF_MAILTO` (or one shared `CONTACT_EMAIL`) | Free | Low | Keep. Send `mailto` on every call (none today: `server.py:1684`, `1770`, `1882`). |
| Retraction Watch (via Crossref) | `check_retractions` | Crossref `works/10.1037/a0017838` returns `updated-by` correction (source `publisher`) | Retraction Watch data is merged into Crossref `update-to`/`updated-by` with `source: retraction-watch`; list with `filter=update-type:retraction`; full CSV in `gitlab.com/crossref/retraction-watch-data`, refreshed each working day | as Crossref | Free | Low | Keep. Add a periodic re-check of every cached and archived DOI (FUNC-26). Optionally mirror the CSV for offline checks. |
| DataCite REST | `resolve_doi` fallback; adapter not exposed | 200 | Public, no key for reads | none | Free | Low | Keep; add as a `search` source (datasets, software). Adapter exists: `research_mcp/adapters/datacite.py`. |
| doi.org content negotiation | `get_doi_citation` | 200 `application/x-bibtex` | Works for Crossref and DataCite DOIs | none | Free | Low | Keep as one citation backend; add local CSL rendering for non-DOI items. |
| Unpaywall | `download_paper_by_doi` | without `email`: 422 "Email address required"; with email: 200 | Email required on every call; code default `research-mcp@example.com` silently disables it (`server.py:1611`, `1898`) | `UNPAYWALL_EMAIL` | Free | Low | Keep; make the contact email a required single setting. Also take OA links from OpenAlex `best_oa_location`. |
| CORE v3 | `search_core`, `get_core_work`, `download_core_paper` | keyless: 429 (first call timed out at 25 s) | Unregistered rate "one batch or five single requests per 10 seconds"; registered free key is faster; commercial use allowed under T&C; asks for citation | `CORE_API_KEY` | Free-key | Medium: slow, low quota | Keep (grey literature, theses). Do not send the CORE bearer token to third-party download hosts (FUNC-14). |
| Europe PMC REST | `search_europe_pmc` | 200 | Public; cursorMark paging | none | Free | Low | Keep. Add full-text retrieval for PMC OA (`/{PMCID}/fullTextXML`). Covers PubMed and preprints (`SRC:PPR`). |
| OpenCitations Index v2 | `get_citations` | `citation-count/doi:10.1037/a0017838` 200 (`154`) | Public; optional access token recommended | add `OPENCITATIONS_TOKEN` (optional) | Free | Low | Keep; merge with OpenAlex and S2 into one `citations` tool. |
| ClinicalTrials.gov v2 | `search_clinical_trials` | 200 | v2 is current (classic API retired) | none | Free | Low | Keep as a `search` source. |
| OSF via SHARE v3 | `search_osf`, `search_psyarxiv` | 200 with `Accept: application/vnd.api+json` (HTML otherwise; code sends the header) | Public; covers all OSF preprint providers (PsyArXiv, SocArXiv, etc.) | none | Free | Medium: SHARE response shape is complex | Keep; merge PsyArXiv into an OSF `provider` filter. Add fetch of preprint PDFs (`https://osf.io/{guid}/download`). |
| DSpace@MIT | `search_mit_dspace`, `get_mit_dspace_item` | `/server/api` 200, DSpace 8.2; discover 200 | DSpace 7+ REST (HAL JSON) | none | Free | Low to medium: repository-specific `dc.type` vocab | Keep; one `repository` source with `repo=mit`. |
| Harvard DASH | `search_harvard_dash`, `get_harvard_dash_item` | 200, DSpace 8.0 | same | none | Free | same | Keep (`repo=harvard`). |
| Cornell eCommons | `search_cornell_ecommons`, `get_cornell_ecommons_item` | 200, DSpace 8.2 | same | none | Free | same | Keep (`repo=cornell`). |
| UPenn ScholarlyCommons | `search_penn_scholarly`, `get_penn_scholarly_item` | 200, **DSpace 7.6** (code and docs say DSpace 8, `server.py:1141`, `1167`) | same REST contract; works | none | Free | same | Keep (`repo=penn`); correct the version label. Registry makes adding any other DSpace 7+ repository a config entry. |
| GitHub REST | 3 GitHub tools | not verifiable from this sandbox (session proxy blocks `/search`) | `X-GitHub-Api-Version: 2022-11-28` (used, `server.py:3626`) is supported until at least 2028-03-12; `2026-03-10` is the first calendar version with breaking changes. Code search requires auth and has a low per-minute limit | `GITHUB_TOKEN` | Free-key | Low | Keep. Merge into one `code` source group. |
| AWS docs search proxy | `search_aws_docs` | 200 (89 KB) | Undocumented internal endpoint of the docs site | none | Free | **High fragility** | Replace with the official **AWS Knowledge MCP Server** (`https://knowledge-mcp.global.api.aws`; `initialize` returned 200, no auth) or call it as an upstream. |
| Microsoft Learn site search | `search_microsoft_docs` | 200 | Undocumented site API | none | Free | **High fragility** | Replace with the official **Microsoft Learn MCP Server** (`https://learn.microsoft.com/api/mcp`; `initialize` returned 200, no auth). |
| Google Developer Knowledge API | `search_gcp_docs` | v1alpha and v1 both 403 without a key ("unregistered callers") | API and MCP server GA 2026-04-16; v1 current; `SearchDocumentChunks` `page_size` max raised 20 to 100 (2026-07-09); filter on `data_source`, `update_time`, `uri` since 2026-04-09; `relevance_score` on chunks; `AnswerQuery` method GA | `GOOGLE_DEVKNOWLEDGE_API_KEY` | Free-key (GCP project) | Low | Keep; move `v1alpha` to `v1` (`server.py:2758`), raise clamp (`2838`), verify filter field name against v1 docs. Covers all Google developer docs, not only Cloud. |
| Google Programmable Search JSON API | `search_iam_docs` | 400 for a dummy key (endpoint alive) | Closed to new customers; retires 2027-01-01. New engines since 2026-01-20 limited to 50 listed sites | `GOOGLE_PSE_CX` + `GOOGLE_DEVKNOWLEDGE_API_KEY` | Metered | Dead end | **Remove** (owner decision). |
| Vertex AI Search (Discovery Engine) | `search_iam_docs` provider | not probed (needs ADC) | Per a Brave-published article, renamed "Agent Search" inside Gemini Enterprise Agent Platform; searches only configured sites | `VERTEX_AI_*` + ADC | Paid | High setup cost | **Remove** with `search_iam_docs`. |
| Brave Search API | `search_iam_docs` provider | 422 for a dummy token | Free tier removed Feb 2026; $5 per 1,000 queries with $5/month credit (credit tied to attribution); code comment still assumes the free tier (`server.py:3178`) | `BRAVE_SEARCH_API_KEY` | Metered | Medium | **Remove** with `search_iam_docs`. If general web search is ever wanted again, make it a separately opt-in source. |
| SerpAPI | `search_iam_docs` provider | not probed | Free 250 searches/month (50/hour); paid from $25/month for 1,000 | `SERPAPI_API_KEY` | Metered | Medium; scraping-based | **Remove** with `search_iam_docs`. |
| IAM doc site crawler | `index_iam_project` etc. | sitemaps not re-probed | Only 10 pages are in the live index (opa, syncope) | none | Free | Medium: sitemaps and site layouts change | Keep as a generic "docs site" source: on-demand `fetch` of a URL plus optional site crawl job, under an allowlist. |

### 3.1 High-value sources missing today

Probed 2026-10-19 unless marked otherwise. Ordered by value for this owner (IAM, authorization, AI governance, plus psychology and biomedical topics visible in tool docstrings).

| Source | What it adds | Live check | Auth (env var) | Tier | Upkeep |
|---|---|---|---|---|---|
| IETF Datatracker API and RFC Editor | RFCs and Internet-Drafts (OAuth, OIDC-adjacent, SCIM, GNAP) with status and obsoletes/updates | `datatracker.ietf.org/api/v1/doc/document/?title__icontains=oauth&type__slug=rfc` 200 (33 hits); `rfc-editor.org/rfc/rfc6749.json` 200 | none | Free | Low |
| NIST publications (SP 800 series etc.) | Standards such as SP 800-207, 800-162 | NIST SPs carry DOIs under prefix `10.6028`, reachable via Crossref `filter=prefix:10.6028`; no CSRC JSON API found (a guessed feed URL returned 404) | none | Free | Low via Crossref; crawl CSRC pages for drafts |
| NIST NVD CVE API 2.0 | Vulnerabilities for IAM products (Keycloak etc.) | `services.nvd.nist.gov/rest/json/cves/2.0` 200 | `NVD_API_KEY` (optional, raises limit) | Free-key | Low |
| PubMed / NCBI E-utilities | Native PubMed search, MeSH, links to PMC | `esearch.fcgi?db=pubmed` 200 | `NCBI_API_KEY` (optional; about 3 req/s without, 10 with) | Free-key | Low. Europe PMC already covers most of PubMed, so this is second priority |
| bioRxiv / medRxiv API | Preprint metadata and PDFs | `api.biorxiv.org/details/...` 200 | none | Free | Low. API is by date range or DOI only (no keyword search); discover via Europe PMC `SRC:PPR` or Crossref `posted-content`, fetch via this API |
| SSRN | Law, policy, governance working papers | no public API; reachable via Crossref `filter=prefix:10.2139` (200) and OpenAlex | none | Free | Low (metadata); PDFs often behind login |
| Zenodo | Datasets, software, reports with DOIs | `zenodo.org/api/records` 200 | `ZENODO_TOKEN` (optional) | Free | Low |
| OpenAIRE Graph API | European aggregator (pubs, datasets, projects, funders) | `api.openaire.eu/graph/v1/researchProducts` 200 | none for basic use | Free | Low |
| HAL | French open archive | `api.archives-ouvertes.fr/search` 200 | none | Free | Low |
| DOAJ | OA journal articles | `doaj.org/api/search/articles` 200 | none | Free | Low |
| DBLP | CS bibliography (SACMAT, CCS, USENIX), author disambiguation | **202 bot-check page** from this datacenter IP; likely fine from a home IP; full XML dump available | none | Free | Medium (bot protection) |
| ORCID public API | Author identity, works lists | `pub.orcid.org/v3.0/expanded-search` 200 | none for public reads | Free | Low |
| Hugging Face Papers | ML papers with code links; Papers with Code API now redirects to `huggingface.co/papers/trending` | `huggingface.co/api/papers/search` 200 (715 KB unbounded response: cap it) | none | Free | Medium (undocumented response size) |
| ERIC | Education research (psychology adjacency) | `api.ies.ed.gov/eric/` 200 | none | Free | Low |
| NASA ADS | Physics and astronomy, strong citation data | 401 "Missing Authorization" | `ADS_API_TOKEN` | Free-key | Low |
| Lens.org scholarly and patents | Patents plus scholarly (fits the `competitive-landscape` prompt) | 401 | `LENS_API_TOKEN` | Free-key (trial) or Paid | Medium |
| BASE (Bielefeld) | Large OAI aggregator | "Access denied for IP address" (requires IP registration) | IP allowlist | Free (registered) | High setup |
| Google Scholar | Broadest discovery | no official API; only SerpAPI `google_scholar` engine (paid, scraping) | `SERPAPI_API_KEY` | Paid | High; terms risk. Recommend OpenAlex + Semantic Scholar + CORE + Crossref as the Scholar alternative set |
| W3C, OpenID Foundation, FIDO specs | WebAuthn, OIDC, FAPI specs | not probed; no simple public APIs (W3C API needs a key) | varies | Free | Medium: crawl through the docs-site source |

## 4. Findings

Severity: **Critical** (wrong data or silent loss), **High** (a source or core capability broken or misleading), **Medium** (degraded quality, cost, or maintainability), **Low** (polish).

### 4.1 Sources and reach

| ID | Severity | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| FUNC-01 | High | No federated search. A cross-source question needs 10 to 20 separate tool calls, each with different argument names (`max_results` vs `limit`, `year` string vs `year_from` int), different result shapes, and no merging. | 20 `search_*` tools across `server.py:654` to `4524` | One `search` tool over a source registry: concurrent fan-out with per-source timeout and budget, merged results, per-source status (ok, error, rate_limited, skipped_no_key, skipped_unhealthy, latency_ms, total). See section 5. |
| FUNC-02 | High | No cross-source dedupe. The same paper from arXiv, S2, OpenAlex, Crossref, CORE and Europe PMC appears as separate unrelated records. | No shared identifier model in `server.py`; each parser returns its own dict | Normalize identifiers (DOI lowercase without prefix; arXiv id without version; PMID; PMCID; OpenAlex W-id; S2 paperId; CORE id; NCT; RFC number; DSpace handle) and merge on any shared identifier, with a title plus year plus first-author fallback. Return `found_in: [sources]`. |
| FUNC-03 | High | OpenAlex calls fail without a key under the new budget model; `OPENALEX_EMAIL` (mailto) no longer gives a separate pool. `check_retractions` loses its OpenAlex leg too. | Live 429 "Insufficient budget" body; `server.py:2016`, `2019` to `2023`, `4316` | Add `OPENALEX_API_KEY` (Bearer header), track remaining budget from responses in `source_health`, and degrade gracefully with status `rate_limited`. |
| FUNC-04 | High | `search_semantic_scholar` uses `/paper/search/bulk`, which does not accept `limit`. Every call returns up to 1,000 records with abstracts (megabytes into the model context), sorted without relevance. | `server.py:1041` to `1055`; live `limit=3` returned 1,000 records | Use `/paper/search` with `limit`/`offset` for interactive search; keep bulk for jobs only; add `SEMANTIC_SCHOLAR_API_KEY`. |
| FUNC-05 | Medium | Crossref calls never send `mailto`, so they run in the public pool (1 list request per second, concurrency 1), which federated fan-out will hit. | `server.py:1684`, `1770`, `1882`; live headers `x-api-pool: public-array` vs `polite-array` with mailto | One required `CONTACT_EMAIL` setting used for Crossref `mailto`, Unpaywall `email`, and every User-Agent. Remove the `example.com` fallback (`server.py:1611`, `4199` to `4201`). |
| FUNC-06 | Medium | arXiv base URL is `http://` and depends on a 301 redirect. | `server.py:42`; live 301 to https | Use `https://export.arxiv.org/api/query`. |
| FUNC-07 | Medium | OpenAlex field drift: `concepts` filter and `last_known_institution` are deprecated; `per-page` clamp of 200 exceeds the documented max of 100. | `server.py:2045` to `2048`, `2147`, `2254`, `2136` | Use `topics`, `last_known_institutions`, max 100. Add a contract test per source against a recorded fixture refreshed monthly. |
| FUNC-08 | High | Retrieval covers only arXiv, Unpaywall/S2 OA links, and CORE. Sources that expose files cannot be fetched into the cache: DSpace bitstreams (listed by `get_*_item` but never downloaded), OSF preprint `download_url`, Europe PMC / PMC OA full text, OpenAlex `best_oa_location.pdf_url`, bioRxiv. The "harv", "penn" ids in the live DB show the owner worked around this by downloading manually and calling `index_paper` with invented ids. | `server.py:1393` to `1428` (bitstream links only), `2330` (OSF download_url unused), `1892` to `1944` (OA chain); no code path creates `harv`/`penn` ids | One `fetch(work_or_url)` tool that resolves the best legal OA location across all sources in a ranked order (arXiv, PMC, repository bitstream, Unpaywall/OpenAlex OA location, CORE, OSF), validates content type, hashes, caches with expiry, and records provenance. |
| FUNC-09 | Medium | Vendor docs use two undocumented site endpoints (AWS proxy, Microsoft Learn site search) that can change without notice; both vendors now publish official, unauthenticated MCP servers. | `server.py:2754`, `2760`; live `initialize` 200 for both MCP endpoints | Proxy the AWS Knowledge MCP and Microsoft Learn MCP as upstream sources (or recommend the owner add them as separate MCP servers and drop these two tools). Move GCP to Developer Knowledge `v1`. |
| FUNC-10 | Medium | `search_iam_docs` is a 4-provider fallback chain, three of which are now paid or closing (Google CSE retires 2027-01-01, Brave free tier gone, Vertex renamed and site-limited). The docstring says Google PSE but the code tries Vertex first. | `server.py:3237` to `3357`, `3257` to `3267`, `3178` | Remove per owner decision, with its 8 env vars and `google-auth` dependency. Cover IAM docs with: docs-site source (fetch plus crawl), IETF Datatracker/RFC Editor, NIST via Crossref, vendor MCPs. |
| FUNC-11 | Medium | Penn is DSpace 7.6, not 8; the code labels all four as DSpace 8. Works today because the REST contract is shared, but version-specific fixes will be misapplied. | Live `dspaceVersion`; `server.py:1141`, `1167` to `1172` | Store `dspace_version` per repository in the registry and record it in `source_health` on first contact. |
| FUNC-12 | Low | 8 DSpace tools, 2 OSF tools, 3 CORE tools, 3 OpenAlex tools, 2 S2 tools are per-source copies of the same verbs (search, get, download). | Section 2 | Merge tools, keep every source: `search(sources=...)`, `get_work(id)`, `fetch(id)`. |
| FUNC-13 | Medium | No per-source health or quota visibility; a dead or throttled source just raises or returns an error string. | e.g. `server.py:693` to `694` `raise_for_status` inside a tool; S2 retry loop `996` to `1009` | `source_health` table plus a `research://sources` resource showing key present, last success, last error, quota or budget remaining, reset time. |
| FUNC-14 | High | `download_core_paper` sends `Authorization: Bearer <CORE_API_KEY>` to whatever host CORE's `downloadUrl` points to, which is often a third-party repository. | `server.py:2693` to `2698` | Send credentials only to their origin (the unused `ScopedCredential` in `research_mcp/security.py` already models this). Flag for the security reviewer. |

### 4.2 Retrieval, reading, citation

| ID | Severity | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| FUNC-15 | Medium | Downloads do not check content type. Paywall or landing HTML gets saved as `.pdf`, then extraction fails and the result says `downloaded_but_indexing_failed`. | `server.py:750` to `755`, `1964` to `1971`, `2693` to `2701` | Check `Content-Type` and `%PDF` magic, cap bytes (config already has `max_download_bytes`, unused), record HTTP status and final URL. |
| FUNC-16 | Medium | `get_paper_text`, `list_indexed_papers`, `index_all_papers` details and `fetch_*` with a raised `max_chars` are unbounded; `query_papers` returns full 1,500-char chunks for every hit. | `server.py:294` to `336`, `338` to `361`, `876` to `882`, `2963` | Bounded envelopes with cursors (config `max_response_bytes = 65,536` exists but is unused, `research_mcp/config.py:25`). `read` returns a page or section window plus `next_cursor`; search returns snippets, not full chunks, by default. |
| FUNC-17 | Medium | Citation export exists only per DOI through doi.org. No BibTeX or CSL for arXiv-only items, DSpace items, RFCs, web docs, or a whole collection; no RIS. | `server.py:1790` to `1835` | `cite(ids or collection, format=bibtex|csl-json|ris|text, style)`: doi.org negotiation when a DOI exists, otherwise render from stored normalized metadata with citeproc. Store a CSL-JSON snapshot on every work so discarded items stay citable. |
| FUNC-18 | Medium | Citation graph is split: OpenCitations (`get_citations`), S2 (`get_semantic_scholar_paper` refs/cites, first 20), OpenAlex (`referenced_works`, first 30, ids only). None returns titles together or merges. | `server.py:4455`, `1108` to `1120`, `2209` to `2217` | One `citations(id, direction)` that unions OpenCitations, OpenAlex and S2, dedupes by DOI, and hydrates titles in one batched OpenAlex call. |
| FUNC-19 | Low | `get_doi_citation` accepts any `style` string and any `format`; unknown formats silently fall back to text. | `server.py:1813` to `1818` | Validate against an enum; list supported CSL styles in the tool schema. |

### 4.3 Local data, integrity, cache behavior

| ID | Severity | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| FUNC-20 | Critical | **Duplicate works from inconsistent arXiv id normalization.** Live DB: 176 file-backed rows point to only 122 distinct files; 54 files have two rows each, one versioned with a title (e.g. `2410.18291v1`) and one unversioned with an empty title (`2410.18291`). Mechanism: `download_paper` stores the row under the *versioned* id from the arXiv Atom `<id>` (`_parse_entry`, `server.py:569`; `upsert_paper` keys on `meta["arxiv_id"]`, `167`), while the file is named by the caller's unversioned id (`735`). `index_all_papers` derives the id from the file stem (`846`), so `needs_reindex("2410.18291")` is always true (`849`); when the arXiv metadata call fails (3 s limiter, timeouts) the fallback meta has no title (`861` to `863`) and a second row is created. Even on success, every run re-fetches metadata and re-chunks those 54 files. Effects: duplicate chunks inflate FTS and semantic results (the same passage appears twice), counts are wrong (about 132 unique works, not 186), and `remove_paper("2410.18291")` leaves the titled copy. | Coordinator read-only DB check; code lines cited | Normalize identifiers at the boundary: arXiv id stored without version, version kept separately. Unique constraint on `(scheme, value_norm)`. One work per paper; files and versions hang off it. Import step dedupes and reports (section 6.3). |
| FUNC-21 | High | `index_all_papers` turns every `_` in a file stem into `/`, so `doi_10.1145_3649835.pdf` becomes id `doi/10.1145/3649835` (stored by `download_paper_by_doi` as `doi:10.1145/3649835`) and `core_123.pdf` becomes `core/123` (vs `core:123`). Each run creates further duplicates and sends bogus ids to arXiv. | `server.py:846`, `1960`, `1997`, `2689`, `2724` | Never derive identity from file names; keep a `files` table keyed by sha256 that maps to a work. |
| FUNC-22 | High | Web documentation pages live in the `papers` table with a URL in `pdf_path` and synthetic ids `iam:<project>:<sha1-16>`; nothing distinguishes a web page from a paper except the id prefix. | `server.py:3478`, `3511`; live: 10 rows `iam:opa:*`, `iam:syncope:*` | v2 `documents.kind` (pdf, html, text) and `origin_url`; web pages may have no work row, or a work of type `webpage`. |
| FUNC-23 | High | Crawled HTML is whitespace-collapsed to a single line (`\s+` to space), and `chunk_pages` splits only on `\n`, so each web page becomes **one chunk of unlimited size** (Syncope reference guides are hundreds of KB). FTS snippets still work, but `query_papers` returns the entire page per hit and embeddings see only the first 512 tokens. | `server.py:3372`, `489` to `499`, `3502` | Chunk by characters or tokens with sentence boundaries, not by lines; keep heading structure from HTML (`h1` to `h3`). |
| FUNC-24 | Medium | Chunking quality: overlap is a raw character slice (cuts mid-word, `507`); next chunk's `page_start` is set to the previous page end even when the overlap text came from an earlier page (`510`); heading regex matches many body lines (e.g. any line starting with a capital letter after a single letter, `462`); references and boilerplate are indexed; scanned PDFs yield zero chunks with no OCR and no warning. | `server.py:456` to `520`, `445` to `453` | Versioned chunker: token-based windows (about 300 to 500 tokens, 10 to 15% overlap) on sentence boundaries, `char_start`/`char_end` offsets, section from PDF outline (`doc.get_toc()`) when present, flag empty-text PDFs as `needs_ocr`. Record `chunker_version` so re-chunking is detectable. |
| FUNC-25 | Medium | `total_pages` stores the count of pages that had text, not the PDF page count, so page math and stats are wrong for PDFs with blank or image pages. `content_hash` is SHA-256 truncated to 16 hex chars, so it cannot serve as a file identity or be compared with external checksums. | `server.py:452`, `641`, `818`, `867`; `528` | Store `page_count = len(doc)` and full 64-char `sha256`. |
| FUNC-26 | Medium | No refresh of stale entries. Indexed dates span 2026-02-08 to 2026-04-16; nothing re-checks arXiv versions, retraction status, or OA availability of cached items. | No refresh code path; `check_retractions` only on demand | `works.metadata_refreshed_at`, `retraction_checked_at`; a refresh job that re-checks cached plus archived works (cheap: Crossref and OpenAlex batch by DOI filter). Surface "retracted since cached" in the expiry review. |
| FUNC-27 | Medium | `PaperIndex` never enables `PRAGMA foreign_keys`, so the declared `ON DELETE CASCADE` is inert; code deletes chunks manually. No `user_version` (live value 0). FTS triggers are created only if the FTS table creation succeeds in the same call, so a partially created schema never gets triggers. | `server.py:82` to `85`, `111`, `117` to `146` | v2 opens via `SQLiteRepository` (FK on, `user_version`, explicit migrations). |
| FUNC-28 | Medium | FTS5 configuration: `arxiv_id` is an indexed, porter-stemmed column, so id fragments match as text; title and abstract are not indexed at all, so a title search only hits body chunks; no `prefix` index although `term*` is advertised; heading and body share equal BM25 weight. `search_iam_index` builds the FTS query without the literal-retry fallback, so operator syntax errors raise. | `server.py:119` to `124`, `3546` to `3556` vs `221` to `237` | `chunks_fts(content, section, title, doc_id UNINDEXED, tokenize='porter unicode61 remove_diacritics 2', prefix='2 3')`; a small `works_fts(title, abstract, authors)`; `bm25(chunks_fts, 1.0, 2.0, 3.0)`. One search code path. |
| FUNC-29 | High | Semantic search silently covers a small subset: `embeddings.duckdb` is 1.3 MB, while 11,403 chunks x 384 dims x 4 bytes is about 17.5 MB before index overhead, so at most about 7% of chunks are embedded. `embed_chunks` must be run by hand and nothing reports coverage in `semantic_search` results. | Live file size; `server.py:4070` to `4120`, `4124` to `4179` | In v2, embed at fetch time (bge-small embeds a 30-page paper in seconds on CPU); include `coverage` in every semantic result; hybrid ranking (BM25 plus vector, reciprocal rank fusion). |
| FUNC-30 | High | Embeddings are keyed by `chunk_id`, which changes whenever a paper is re-indexed (`upsert_paper` deletes and re-inserts chunks with new AUTOINCREMENT ids). Old vectors become orphans (excluded only by the JOIN) and new chunks are unembedded. `content_hash` is stored per vector but never checked. The model name is not stored per row and the column is `FLOAT[384]`, so changing `EMBED_MODEL_NAME` breaks or silently mixes vector spaces. | `server.py:170` to `205`, `4029` to `4035`, `4106` to `4111` | Key vectors by `(content_sha256, model)`; store `model` and `dim`; garbage-collect unreferenced vectors with the cache sweep. |
| FUNC-31 | Medium | Query embedding uses `model.embed()`; BGE retrieval expects the query instruction prefix (fastembed provides `query_embed()`), so recall is lower than it should be. HNSW uses `hnsw_enable_experimental_persistence`, which DuckDB warns can corrupt on unclean shutdown, and the query shape (JOIN plus WHERE, `array_cosine_similarity DESC`) means the HNSW index is not used anyway. | `server.py:4011` to `4014`, `4027`, `4146` to `4154` | Use `query_embed` for queries and `passage_embed` for chunks. At cache scale (tens of thousands of chunks) use exact search: `sqlite-vec` in the same SQLite file, or numpy over a BLOB column. Drops the second database file and the DuckDB dependency for embeddings. |
| FUNC-32 | Medium | `analytics_sql` runs on a DuckDB connection with no file sandbox: `read_csv`, `read_text`, or a bare `'path'` table reference can read any local file; only `dataset_query` rewrites reader paths, and its regex misses `read_text`, `read_blob`, `glob` and bare path literals. The SQLite path is interpolated into `ATTACH` with an f-string. | `server.py:3793`, `3802` to `3821`, `3939` to `3966` | Functionally: merge into one opt-in expert `sql` tool (config flag `RESEARCH_MCP_ENABLE_EXPERT_SQL` already exists). Use DuckDB `enable_external_access=false` plus explicit allowed directories. Flag for the security reviewer. |
| FUNC-33 | Medium | `index_paper` accepts any id and any local `pdf_path`; `download_*` accept any `download_dir`. Identity and storage location are caller-controlled, which is how invented ids (`harv...`, `penn...`) entered the DB with no provenance. | `server.py:777` to `797`, `720`, `733`, `1842`, `2649` | v2: files live only under the data root (relative `storage_path`); identity comes from the source record; a local import tool records `source = local_file` with original path as provenance. |
| FUNC-34 | Medium | No provenance: the DB does not record which source, query, URL, license, OA status or HTTP result produced each row. Crossref publication date ignores `issued` and uses only `published-print` then `published-online`, so many works have empty dates. | `server.py:174` to `190`; `1636` to `1638` | `source_records`, `searches`, `files.final_url/http_status/etag`, `documents.license/oa_status`; Crossref date from `issued` first. |
| FUNC-35 | Low | `PAPER_INDEX.md` is a hand-written snapshot (122 papers, 11,385 chunks, 2026-04-08) that disagrees with the live DB (186 rows, 11,403 chunks). | `PAPER_INDEX.md:4` to `6` | Replace with a generated MCP resource (`research://cache/index`). |

### 4.4 Architecture items that affect the tool surface

| ID | Severity | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| FUNC-36 | High | The modern foundation is built but unwired: `research_mcp/repository.py` (versioned schema with works, identifiers, documents, retrievals, extractions, document_chunks, source_records, collections, jobs), `config.py`, `security.py` (safe downloader, scoped credentials), `jobs.py`, `cache.py`, `errors.py`, `prompts.py`. `server.py` imports only adapters and models. | `server.py:4191` to `4196`; no other `research_mcp` import | v2 composes these modules; `server.py` becomes registration only. |
| FUNC-37 | Medium | `repository.py` legacy migration would carry today's integrity problems forward: unknown prefixes (`harv...`, `penn...`) fall through to scheme `arxiv` (`repository.py:305` to `311`); versioned and unversioned arXiv rows become two works; `iam:<project>:<hash>` becomes scheme `iam` with no URL; chunk ids become strings (`legacy:<int>`), which breaks the embeddings link; embeddings are not migrated; `document_chunks` has no FTS table; no lifecycle fields. It also runs automatically inside `initialize()`. | `repository.py:244` to `311`, `115` to `140` | Replace with an explicit, optional `import_legacy` job (section 6.3); add lifecycle columns; add FTS. |
| FUNC-38 | Medium | No MCP resources or prompts are registered even though `prompts.py` defines five research prompts. | no `@mcp.resource` / `@mcp.prompt` in `server.py` | Register prompts; expose read-only views as resources (section 5.3). |
| FUNC-39 | Low | Multi-step work (crawl, `index_all_papers`, `embed_chunks` up to 10,000 chunks) runs synchronously inside one tool call with no progress or cancellation. | `server.py:829`, `3442`, `4070` | `jobs` table plus MCP progress notifications; long tools return a `job_id`. |
| FUNC-40 | Low | SSE transport option uses the deprecated MCP HTTP+SSE transport. | `server.py:4603` to `4610` | Streamable HTTP for remote use; stdio stays default (owner of transport is the platform reviewer). |

## 5. Proposed v2 tool surface

Principle: **merge tools, keep and grow sources.** 53 tools become 14, while sources grow from about 25 to about 40 through a registry. Every source is a registry entry with capabilities, auth env var, rate policy, cost tier and health, so adding a DSpace repository, a preprint server or a docs site is configuration plus a small adapter.

### 5.1 Source registry and groups

Each entry: `id`, `group`, `capabilities` (search, get, fetch, citations, authors), `auth_env`, `cost_tier`, `rate_policy`, `default_enabled`, `adapter_version`.

| Group | Sources |
|---|---|
| `scholarly` | openalex, semantic_scholar, crossref, core, datacite, dblp, openaire, doaj, zenodo, hal, ads (keyed), lens (keyed, off by default) |
| `preprints` | arxiv, osf (provider filter: psyarxiv, socarxiv, ...), biorxiv, medrxiv, ssrn (via Crossref prefix), hf_papers |
| `biomed` | europe_pmc, pubmed, clinical_trials |
| `repositories` | dspace:mit, dspace:harvard, dspace:cornell, dspace:penn (add more DSpace 7+ by config) |
| `standards` | ietf (Datatracker plus RFC Editor), nist (Crossref prefix 10.6028 plus CSRC pages), nvd |
| `vendor_docs` | aws_knowledge (upstream MCP), ms_learn (upstream MCP), google_devknowledge, docs_site (allowlisted crawl and fetch: Keycloak, Ory, OPA, Vault, Syncope, FreeIPA, OpenID, W3C, ...) |
| `code` | github (repos, code, readme) |
| `integrity` | crossref_updates, retraction_watch, openalex_retracted |
| `education` | eric |
| `cache` | local FTS plus vectors |

### 5.2 Tools

| v2 tool | Replaces (v1) | Behavior |
|---|---|---|
| `search(query, sources="auto" or list or groups, filters{year_from, year_to, type, oa_only, provider, repo}, limit, per_source_limit, cursor, detail="compact")` | all 20 `search_*` tools, `search_openalex_authors` excluded | Federated fan-out with per-source timeout and budget. Returns merged, deduped works (`found_in`, best identifiers, OA flag, cached state) plus `source_status[]` (ok, error, rate_limited, skipped_no_key, skipped_unhealthy, total, latency_ms). Compact by default; cursor per source encoded in one opaque cursor. `sources="auto"` picks groups by query and filters. |
| `get_work(id)` | `get_paper_metadata`, `get_semantic_scholar_paper`, `resolve_doi`, `get_openalex_work`, `get_core_work`, 4 `get_*_item` DSpace tools | Accepts any identifier form (`doi:`, `arxiv:`, `pmid:`, `pmcid:`, `openalex:`, `s2:`, `core:`, `nct:`, `rfc:`, DSpace handle or UUID, URL). Merges records across sources; includes OA locations, files available, retraction status, cache state. |
| `fetch(id_or_url, prefer="pdf"|"html"|"xml", pin=false)` | `download_paper`, `download_paper_by_doi`, `download_core_paper`, `index_paper`, `fetch_cloud_doc_page`, `fetch_github_readme`, `index_iam_project` (single page) | Resolves best legal OA location across sources, downloads safely (content-type, size, redirects, scoped credentials), extracts, chunks, embeds, caches with `expires_at = now + 30 days`. Returns a document handle and a short summary, not the text. Re-fetch of a discarded item reuses its stored `fetch_recipe`. |
| `read(doc_id, pages or section or chunk range, cursor, max_chars)` | `get_paper_text` | Bounded window with `next_cursor`; updates `last_accessed_at`. |
| `search_cache(query, mode="hybrid"|"keyword"|"semantic", doc_ids, collection, limit)` | `query_papers`, `semantic_search`, `search_iam_index` | One path over FTS plus vectors with snippets, page numbers, coverage. |
| `cite(ids or collection_id, format="bibtex"|"csl-json"|"ris"|"text", style="apa")` | `get_doi_citation` | Works for every item, including archived and discarded ones, from stored CSL snapshots. |
| `citations(id, direction="citing"|"references"|"both", limit, cursor)` | `get_citations`, refs and cites parts of S2 and OpenAlex tools | Union of OpenCitations, OpenAlex, S2, hydrated with titles. |
| `authors(query or orcid)` | `search_openalex_authors` | OpenAlex plus ORCID plus DBLP. |
| `check_integrity(ids or "cache")` | `check_retractions` | Crossref updates (including Retraction Watch source), OpenAlex flag; `"cache"` re-checks every cached and archived work. |
| `library(action="list"|"pin"|"unpin"|"archive"|"discard"|"restore"|"review_expiring", ids, archive_to)` | `list_indexed_papers`, `remove_paper`, `index_stats`, `list_iam_indexed` | Lifecycle management (section 6.2). `review_expiring` returns the items due within N days with title, citation, size, last access, integrity changes, so the owner can decide archive or discard. Never deletes without an explicit `discard`. |
| `collections(action="create"|"add"|"remove"|"list"|"show"|"export", ...)` | none (gap) | Saved sets of works; adding a work to a collection can auto-pin its documents. Export via `cite`. |
| `crawl_site(site, max_pages)` | `index_iam_project` | Job; allowlisted docs sites only; pages cached with the same 30-day lifecycle. |
| `jobs(action="status"|"cancel"|"list", job_id)` | none | For crawl, bulk fetch, refresh, re-embed, legacy import. |
| `sql(query, target="cache"|"datasets")` | `analytics_sql`, `dataset_query`, `list_datasets` | Expert, disabled unless `RESEARCH_MCP_ENABLE_EXPERT_SQL` is set; read-only, external access off, allowed dirs only. |
| `embedding_stats`, `embed_chunks`, `index_all_papers`, `search_iam_docs`, `search_psyarxiv` | | Removed: embedding at fetch time, coverage in `library` stats; legacy import is a job; `search_iam_docs` decommissioned; PsyArXiv is an OSF `provider`. |

### 5.3 Resources and prompts

Resources (read-only, cheap for clients to attach):
- `research://sources` : registry plus health (key present, last ok, last error, budget or quota left, reset time).
- `research://work/{work_id}` : merged metadata, identifiers, CSL snapshot, state.
- `research://doc/{doc_id}/text{?page}` : page text.
- `research://collection/{collection_id}` : members plus notes.
- `research://cache/expiring` : items due for archive-or-discard decision (drives the review flow).
- `research://cache/index` : generated replacement for `PAPER_INDEX.md`.

Prompts: register the five in `research_mcp/prompts.py` (`fact-check-claim`, `literature-review-plan`, `literature-matrix-generator`, `source-bias-evaluator`, `competitive-landscape`) plus `review-expiring-items` (walks the owner through `research://cache/expiring` and calls `library(archive|discard)`) and `cross-source-verify` (compare one work across sources and report metadata disagreements).

Asking the owner before expiry: where the client supports MCP elicitation, `library(review_expiring)` can elicit archive or discard per item; otherwise the `review-expiring-items` prompt plus the `research://cache/expiring` resource, optionally triggered by a scheduled task in the host. Items past `expires_at` with no decision stay in state `expiring` (overdue) and keep their files.

## 6. Data model v2 and legacy import

### 6.1 Design choices

1. **Work vs document vs file.** A *work* is the intellectual item (one per paper, regardless of version or source). A *document* is a cached manifestation the owner can keep or discard (a PDF, an HTML page, a PMC XML), and it carries the lifecycle. A *file* is bytes on disk keyed by full sha256. Web pages are documents with `kind = 'html'` and may link to a work of type `webpage`.
2. **Identifiers are normalized at the boundary** and unique per `(scheme, value_norm)`, which is the dedupe key across sources and across time. arXiv ids drop the version (`2410.18291`); the version lives on the file (`version_label = 'v1'`). DOIs are lowercased without `https://doi.org/` or `doi:`.
3. **Metadata outlives files.** Discarding deletes file bytes, chunks and vectors, but keeps the work, identifiers, CSL snapshot, source records and a `fetch_recipe` (best URL plus source plus expected sha256), so re-fetch is one call and citation still works.
4. **One SQLite file** with FTS5 and `sqlite-vec` (or BLOB vectors) instead of SQLite plus DuckDB for embeddings. DuckDB stays only behind the expert `sql` tool.

### 6.2 Schema (SQLite, `PRAGMA user_version = 2`, `foreign_keys = ON`, WAL)

```sql
CREATE TABLE works (
  work_id TEXT PRIMARY KEY,              -- ULID
  work_type TEXT NOT NULL,               -- article, preprint, thesis, report, rfc, standard, dataset, software, webpage, trial
  title TEXT NOT NULL,
  title_norm TEXT NOT NULL,              -- casefolded, punctuation-stripped, for fuzzy dedupe
  authors_json TEXT NOT NULL DEFAULT '[]',
  first_author_norm TEXT,
  year INTEGER,
  published_at TEXT,
  venue TEXT,
  abstract TEXT,
  language TEXT,
  csl_json TEXT NOT NULL,                -- citation snapshot, kept for archived and discarded items
  integrity_status TEXT NOT NULL DEFAULT 'unknown',  -- clean, corrected, expression_of_concern, retracted, unknown
  integrity_checked_at TEXT,
  metadata_refreshed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX works_dedupe_idx ON works(title_norm, year);

CREATE TABLE identifiers (
  scheme TEXT NOT NULL,                  -- doi, arxiv, pmid, pmcid, openalex, s2, core, nct, rfc, handle, dspace_uuid, osf, url, legacy
  value_norm TEXT NOT NULL,
  value_raw TEXT NOT NULL,
  work_id TEXT NOT NULL REFERENCES works(work_id) ON DELETE CASCADE,
  source TEXT NOT NULL,                  -- which source asserted it
  first_seen_at TEXT NOT NULL,
  PRIMARY KEY (scheme, value_norm)
);
CREATE INDEX identifiers_work_idx ON identifiers(work_id);

CREATE TABLE source_records (
  source_record_id TEXT PRIMARY KEY,
  work_id TEXT REFERENCES works(work_id) ON DELETE SET NULL,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  adapter_version TEXT NOT NULL,
  payload_sha256 TEXT NOT NULL,
  payload_json TEXT,                     -- bounded; may be NULL for large payloads
  search_id TEXT REFERENCES searches(search_id) ON DELETE SET NULL,
  UNIQUE (source, source_id, payload_sha256)
);

CREATE TABLE documents (                 -- the lifecycle unit
  doc_id TEXT PRIMARY KEY,
  work_id TEXT REFERENCES works(work_id) ON DELETE SET NULL,
  kind TEXT NOT NULL CHECK (kind IN ('pdf','html','xml','text')),
  origin_url TEXT,
  landing_url TEXT,
  source TEXT NOT NULL,                  -- arxiv, unpaywall, core, dspace:penn, docs_site:keycloak, local_import, ...
  license TEXT,
  oa_status TEXT,
  state TEXT NOT NULL CHECK (state IN ('cached','pinned','expiring','archived','discarded')),
  cached_at TEXT NOT NULL,
  expires_at TEXT,                       -- cached_at + 30 days; NULL when pinned or archived
  review_notified_at TEXT,               -- when the owner was asked
  pinned_at TEXT,
  archived_at TEXT,
  archive_uri TEXT,                      -- file path or Drive location of the saved copy
  discarded_at TEXT,
  decided_by TEXT,                       -- owner, collection_pin, import
  last_accessed_at TEXT,
  fetch_recipe_json TEXT NOT NULL,       -- source, url, expected sha256, headers policy; enables re-fetch
  CHECK (state <> 'archived' OR archive_uri IS NOT NULL),
  CHECK (state <> 'discarded' OR discarded_at IS NOT NULL)
);
CREATE INDEX documents_state_expiry_idx ON documents(state, expires_at);
CREATE INDEX documents_work_idx ON documents(work_id);

CREATE TABLE files (
  file_id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  sha256 TEXT NOT NULL,                  -- full 64 hex
  size_bytes INTEGER NOT NULL,
  media_type TEXT NOT NULL,
  storage_path TEXT,                     -- relative to data root; NULL after discard
  version_label TEXT,                    -- arXiv v1, v2; publisher version
  page_count INTEGER,
  final_url TEXT, http_status INTEGER, etag TEXT, last_modified TEXT,
  fetched_at TEXT NOT NULL,
  UNIQUE (doc_id, sha256)
);
CREATE INDEX files_sha_idx ON files(sha256);

CREATE TABLE extractions (
  extraction_id TEXT PRIMARY KEY,
  file_id TEXT NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
  parser TEXT NOT NULL, parser_version TEXT NOT NULL,
  chunker_version TEXT NOT NULL, chunk_tokens INTEGER, overlap_tokens INTEGER,
  needs_ocr INTEGER NOT NULL DEFAULT 0,
  extracted_at TEXT NOT NULL
);

CREATE TABLE chunks (
  chunk_id INTEGER PRIMARY KEY,
  extraction_id TEXT NOT NULL REFERENCES extractions(extraction_id) ON DELETE CASCADE,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  ord INTEGER NOT NULL,
  page_start INTEGER, page_end INTEGER, char_start INTEGER, char_end INTEGER,
  section TEXT,
  content TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  UNIQUE (extraction_id, ord)
);
CREATE VIRTUAL TABLE chunks_fts USING fts5(
  content, section, title, doc_id UNINDEXED,
  content='', contentless_delete=1,
  tokenize='porter unicode61 remove_diacritics 2', prefix='2 3'
);                                        -- maintained by triggers on chunks
CREATE VIRTUAL TABLE works_fts USING fts5(title, abstract, authors, work_id UNINDEXED,
  tokenize='porter unicode61 remove_diacritics 2');

CREATE TABLE embeddings (
  content_sha256 TEXT NOT NULL,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL,                   -- float32; or a sqlite-vec vec0 table keyed the same way
  created_at TEXT NOT NULL,
  PRIMARY KEY (content_sha256, model)
);

CREATE TABLE collections (
  collection_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT,
  pin_members INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE collection_items (
  collection_id TEXT NOT NULL REFERENCES collections(collection_id) ON DELETE CASCADE,
  work_id TEXT NOT NULL REFERENCES works(work_id) ON DELETE CASCADE,
  note TEXT, position INTEGER NOT NULL DEFAULT 0, added_at TEXT NOT NULL,
  PRIMARY KEY (collection_id, work_id)
);

CREATE TABLE searches (                  -- provenance of discovery
  search_id TEXT PRIMARY KEY, query TEXT NOT NULL, sources_json TEXT NOT NULL,
  filters_json TEXT NOT NULL, source_status_json TEXT NOT NULL, created_at TEXT NOT NULL
);

CREATE TABLE source_health (
  source TEXT PRIMARY KEY, key_present INTEGER NOT NULL, last_ok_at TEXT, last_error_at TEXT,
  last_error TEXT, rate_limited_until TEXT, budget_remaining TEXT, api_version_seen TEXT
);

CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','running','succeeded','failed','cancelled')),
  params_json TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0, cursor TEXT,
  result_json TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
```

Lifecycle rules:
- `fetch` creates a document in `cached` with `expires_at = cached_at + 30 days`.
- Sweep (on server start and daily): documents with `expires_at` within the review window (for example 5 days) move to `expiring` and appear in `research://cache/expiring`; `review_notified_at` is set when the owner is shown the list.
- Owner decision: `archive` copies the file to the archive location (configurable, for example a synced Google Drive folder), sets `archive_uri`, `archived_at`, clears `expires_at`; `discard` deletes bytes, chunks and vectors not referenced by other documents, sets `discarded_at`, keeps the work, CSL snapshot and `fetch_recipe`.
- No decision: the document stays `expiring` (overdue) with its files. Nothing is deleted without an explicit decision.
- `pin` (or membership in a collection with `pin_members = 1`) sets `pinned`, `expires_at = NULL`. Access does not extend expiry automatically unless the owner wants that; make it a setting.
- Re-fetch of a discarded work creates a new document row; the old row remains as history.

### 6.3 Optional legacy import plus report

Per owner direction this is optional and lightweight: the v2 server starts with an empty cache; `import_legacy(path, mode, dry_run=true)` runs as a job and never modifies the old `arxiv_index.db` (open with `?mode=ro`).

Steps:
1. **Inventory (read-only):** count rows, chunks, distinct `pdf_path`, rows whose file is missing, rows whose `pdf_path` is a URL.
2. **Normalize ids:** versioned arXiv (`2410.18291v1`) to `arxiv:2410.18291` plus `version_label v1`; old-style `cs_0101001` style stems to `cs/0101001`; `doi:...` and `doi/...` to `doi:` lowercase; `core:` and `core/` to `core:`; `iam:<project>:<hash>` to an `html` document with `origin_url = pdf_path` and source `docs_site:<project>`; `harv...`, `penn...` and any other unknown prefix to scheme `legacy` and then a best-effort lookup by title (DSpace search of the matching repository, then Crossref and OpenAlex) to attach real identifiers.
3. **Dedupe:** group rows by `pdf_path` and by normalized identifier. For each of the 54 known pairs keep one work: metadata from the titled row, `published` and categories merged, both raw ids recorded as identifiers (`legacy` scheme for the raw strings).
4. **Re-extract, do not copy chunks:** run the v2 parser and chunker on the 122 distinct files (minutes on a laptop), so chunk ids, offsets, sections and embeddings are consistent with new fetches. Old chunks are imported only for rows whose file is gone (none today, per the corrected live facts) or for the 10 web pages if re-fetch fails.
5. **Enrich:** batch identifier lookup (Crossref by DOI, OpenAlex by DOI or arXiv id) to fill `csl_json`, `year`, `venue`, and run `check_integrity`.
6. **Lifecycle choice (owner picks `mode`):** `cache` (default: every imported document gets `expires_at = import + 30 days` and goes through the normal archive-or-discard review), `archive` (all imported documents archived in place), or `metadata_only` (works and citations only, no files kept).
7. **Report** (returned and saved as JSON plus Markdown under the data root): rows read, works created, duplicate pairs merged (list of id pairs and which metadata won), ids that stayed `legacy` with no match, files re-extracted, extraction failures and `needs_ocr`, chunk counts old vs new, integrity flags found, and a list of every legacy id mapped to its new `work_id` for traceability.

Verification queries the owner can run on the old DB before import (read-only):

```sql
SELECT COUNT(*) AS rows, COUNT(DISTINCT pdf_path) AS paths FROM papers;
SELECT pdf_path, GROUP_CONCAT(arxiv_id) AS ids, COUNT(*) n FROM papers
  WHERE pdf_path NOT LIKE 'http%' GROUP BY pdf_path HAVING n > 1;
SELECT arxiv_id FROM papers WHERE arxiv_id GLOB '*v[0-9]*';
SELECT arxiv_id, pdf_path FROM papers WHERE pdf_path LIKE 'http%';
SELECT arxiv_id FROM papers WHERE arxiv_id NOT GLOB '[0-9][0-9][0-9][0-9].[0-9]*' AND arxiv_id NOT LIKE 'iam:%';
SELECT COUNT(*) FROM chunks c JOIN papers p USING(arxiv_id) WHERE p.title = '' OR p.title IS NULL;
```

## 7. Sources checked (2026-10-19)

Live HTTP probes (this review sandbox, anonymous): `https://export.arxiv.org/api/query`, `https://api.semanticscholar.org/graph/v1/paper/search/bulk`, `https://api.semanticscholar.org/graph/v1/paper/search`, `https://api.openalex.org/works`, `https://api.crossref.org/works`, `https://api.datacite.org/dois`, `https://api.unpaywall.org/v2/`, `https://api.core.ac.uk/v3/search/works`, `https://www.ebi.ac.uk/europepmc/webservices/rest/search`, `https://api.opencitations.net/index/v2/citation-count/`, `https://clinicaltrials.gov/api/v2/studies`, `https://share.osf.io/api/v3/index-card-search`, `https://doi.org/`, `https://proxy.search.docs.aws.com/search`, `https://learn.microsoft.com/api/search`, `https://developerknowledge.googleapis.com/v1alpha` and `/v1`, `https://www.googleapis.com/customsearch/v1`, `https://api.search.brave.com/res/v1/web/search`, `https://{dspace.mit.edu,dash.harvard.edu,ecommons.cornell.edu,repository.upenn.edu}/server/api`, `https://knowledge-mcp.global.api.aws`, `https://learn.microsoft.com/api/mcp`, and the candidate sources in section 3.1.

Documentation and announcements:
- [Crossref: Announcing changes to REST API rate limits](https://crossref.org/blog/announcing-changes-to-rest-api-rate-limits/)
- [Crossref: Retraction Watch data in the REST API](https://crossref.org/documentation/retrieve-metadata/retraction-watch/)
- [OpenAlex: Authentication and rate limits](https://help.openalex.org/api/authentication/) (redirect target of docs.openalex.org rate-limits page)
- [Semantic Scholar API overview](https://www.semanticscholar.org/product/api)
- [CORE API services](https://core.ac.uk/services/api)
- [arXiv API Terms of Use](https://info.arxiv.org/help/api/tou.html)
- [Google Developer Knowledge API release notes](https://developers.google.com/knowledge/release-notes)
- [Brave: Alternatives to the Google Search API before the 2027 shutdown](https://brave.com/learn/google-api-shutdown/) (vendor source; also covers the Vertex AI Search rename)
- [Implicator: Brave drops free Search API tier](https://www.implicator.ai/brave-drops-free-search-api-tier-puts-all-developers-on-metered-billing/)
- [SerpApi pricing](https://serpapi.com/pricing.md)
- [GitHub changelog: REST API version 2026-03-10](https://github.blog/changelog/2026-03-12-rest-api-version-2026-03-10-is-now-available)

Not verified today (stated from code or prior documentation; re-check when keys are configured): Vertex AI Search endpoint behavior, GitHub search endpoints (sandbox proxy blocks them), OpenAlex field deprecations (keyless budget exhausted on this IP), Developer Knowledge v1 filter field name, DataCite and OpenCitations published rate limits.

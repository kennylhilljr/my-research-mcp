# Research MCP v1 to v2: Migration and Cutover (v1)

- **Requirements:** [PRD-migration](../prd/components/PRD-migration-v1.md); **design:** [LLD](../design/LLD-v1.md) section 9.6; [ADR 0001](../adr/0001-new-repo-v1-read-only.md)
- **When:** milestone M4, after M0 to M3 are accepted

## 1. Principles

1. v1 is never modified. Its database is opened immutable; its folder is only read.
2. No credential is re-entered. They move from the v1 client configs into the Keychain.
3. The corpus import is optional. v2 works with an empty cache.
4. Rollback is one config change until v1 is retired.

## 2. Inventory (2026-10-19)

| Item | Where | Notes |
|---|---|---|
| v1 code | `~/Documents/GitHub/my-research-mcp-server` at `568d440` | read-only |
| v1 data | `~/arxiv-papers`: `arxiv_index.db` (34 MB, 186 rows, 11,403 chunks), 123 PDFs, `embeddings.duckdb` | 54 duplicate pairs; 10 web pages stored by URL |
| v1 datasets | `~/research-datasets` | not inspected; open decision O4 |
| v1 credentials | `env` blocks of the v1 server entries in the Claude desktop, Claude Code and OpenClaw configs | names in the review's credential table; values never read during design |

## 3. Cutover steps

| # | Step | Command or action | Check |
|---|---|---|---|
| 0 | (Now, if open decision O1 is accepted) Stop paid web-search calls in v1 | Remove the Programmable Search, Brave and SerpAPI keys from the v1 entries' `env` blocks in each client config | v1 `search_iam_docs` reports the providers unconfigured; no further billed calls |
| 1 | Install v2 and the daemon | `uv tool install <path to my-research-mcp-v2>[pdf,embeddings,macos]`, then `research-mcp install` | `research-mcp doctor` shows the daemon alive |
| 2 | Set the contact email | `research-mcp config set contact.email <address>` | doctor `contact_email` ok |
| 3 | Import credentials (dry run, then real) | `research-mcp secrets import --dry-run`, then `research-mcp secrets import` | Names and fingerprints listed; Credentials page shows each `ok` or `unknown_expiry` |
| 4 | Add new free keys (open decision O2) | Create OpenAlex and Semantic Scholar keys; `security add-generic-password -U -s research-mcp/OPENALEX_API_KEY -a "$USER" -w` | Source board: `openalex` ok |
| 5 | Optional corpus import | `research-mcp import-legacy ~/arxiv-papers --dry-run`, review the report, then without `--dry-run` | Report shows about 132 works, 54 merges, 10 HTML documents |
| 6 | Add v2 to clients beside v1 | Paste the entries from `research-mcp install --print-client-config` (server name `research`) | Each client lists the v2 tools |
| 7 | Parallel use, 3 to 7 days | Use v2 for real work; v1 still available | No blocking issue; source board mostly ok |
| 8 | Disable v1 entries | Set the v1 entries to disabled in each client | Agents use only v2 |
| 9 | Scrub plaintext keys | `research-mcp secrets scrub-client-configs` (backs up each file first) | No secret values remain in client configs |
| 10 | Retire v1 | After 14 days with no fallback and the owner's go-ahead: remove the v1 entries; archive the v1 repository; keep `~/arxiv-papers` until the owner removes it | Owner sign-off |

Rollback before step 10: re-enable the v1 entries (step 8 reversed). The Keychain items stay; v1 does not read them, so the scrubbed values must be restored from the step 9 backups if rollback is needed after scrubbing.

## 4. v1 to v2 tool map

| v1 tool | v2 replacement |
|---|---|
| `search_arxiv` | `search(query, sources=["arxiv"])` |
| `get_paper_metadata` | `get_work("arxiv:<id>")` |
| `download_paper` | `fetch("arxiv:<id>")` |
| `index_paper` | removed: no caller-chosen local paths (ADR 0009); `fetch` indexes automatically |
| `index_all_papers` | `research-mcp import-legacy` (one time) |
| `query_papers` | `search_cache(query, mode="keyword")` |
| `get_paper_text` | `read(doc_id, pages=...)` |
| `list_indexed_papers` | `library(action="list")` |
| `remove_paper` | discard through the cache review only (UI, or `cache_review_decide` inside an open batch); the item goes to the 7-day trash |
| `index_stats` | `library(action="stats")` |
| `search_semantic_scholar` | `search(query, sources=["semantic_scholar"])` |
| `get_semantic_scholar_paper` | `get_work("s2:<id>")` |
| `resolve_doi` | `get_work("doi:<doi>")` |
| `search_crossref` | `search(query, sources=["crossref"])` |
| `get_doi_citation` | `cite(ids=["doi:<doi>"], format=..., style=...)` |
| `download_paper_by_doi` | `fetch("doi:<doi>")` |
| `search_openalex` | `search(query, sources=["openalex"])` |
| `get_openalex_work` | `get_work("openalex:<id>")` |
| `search_openalex_authors` | `authors(query)` |
| `search_osf` | `search(query, sources=["osf"])` |
| `search_psyarxiv` | `search(query, sources=["osf"], provider="psyarxiv")` |
| `search_core` | `search(query, sources=["core"])` |
| `get_core_work` | `get_work("core:<id>")` |
| `download_core_paper` | `fetch("core:<id>")` |
| `search_mit_dspace`, `search_harvard_dash`, `search_cornell_ecommons`, `search_penn_scholarly` | `search(query, sources=["dspace_mit"])` and so on, or `groups=["repositories"]` |
| `get_mit_dspace_item`, `get_harvard_dash_item`, `get_cornell_ecommons_item`, `get_penn_scholarly_item` | `get_work("<handle or uuid>")` |
| `search_europe_pmc` | `search(query, sources=["europe_pmc"])` |
| `check_retractions` | `check_integrity(ids)` |
| `get_citations` | `citations(id)` |
| `search_clinical_trials` | `search(query, sources=["clinical_trials"])` |
| `search_aws_docs` | `search(query, sources=["aws_knowledge"])` |
| `search_gcp_docs` | `search(query, sources=["google_devknowledge"])` |
| `search_microsoft_docs` | `search(query, sources=["ms_learn"])` |
| `fetch_cloud_doc_page` | `fetch(url)` then `read`, or `get_work(url)` for a summary |
| `search_iam_docs` | removed (decision D7, open decision O1); use `search(query, groups=["standards","vendor_docs"])` |
| `index_iam_project` | `crawl_site(site)` |
| `search_iam_index` | `search_cache(query, collection=...)` or `search(query, sources=["docs_site_<name>"])` |
| `list_iam_indexed` | `library(action="list")` filtered by source in the UI |
| `search_github_repos`, `search_github_code` | `search(query, sources=["github"], work_type="repository" or "code")` |
| `fetch_github_readme` | `get_work("github:<owner>/<repo>")` |
| `analytics_sql`, `dataset_query`, `list_datasets` | removed (ADR 0009, open decision O4) |
| `embedding_stats` | `library(action="stats")` (reports coverage) |
| `embed_chunks` | removed: embedding happens at fetch |
| `semantic_search` | `search_cache(query, mode="semantic")` |

The generated v2 inventory (`docs/generated/sources.md`) and this table are the inputs for updating agent instructions that mention v1 tool names.

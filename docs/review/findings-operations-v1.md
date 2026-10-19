# Research MCP v1: Operations, Security, Credentials and Monitoring Review

Scope: operations, security, credentials, monitoring and UI needs for the v2 rebuild.
Code reviewed: read-only copy at `/home/claude/review/v1` (server.py 4,613 lines, `research_mcp/` package, CI, Makefile, README, pyproject).
Review date: 2026-10-19. Secret values were never read or printed; only names appear here.

Owner inputs folded into this design:

1. The core value is horizontal reach (breadth of sources). Per-source health is the main operational signal, and the first UI page is a source board.
2. The local index is a working cache, not a library. Index backups are low priority; config, credential metadata, pins and the archive catalog matter more.
3. Cache retention is 30 days. Nothing is deleted silently: the owner is asked, in batches, whether to archive or discard each expiring item. Unanswered items are kept and asked about again.
4. The archive goes to the locally synced Google Drive "My Drive" folder (default `Research Archive/<year>/`), with a sidecar metadata file per item and a local fallback with a warning.

## 1. Executive summary

* **The hardened foundation in `research_mcp/` is not wired into the running server.** `config.Settings`, `security.py` (SSRF-safe atomic PDF download, confined paths), `cache.py` and `jobs.py` are imported only by tests. server.py imports just the adapters and models (server.py:4191-4196). Every safety flag (`RESEARCH_MCP_AUTH_TOKEN`, `RESEARCH_MCP_ENABLE_EXPERT_SQL`, `RESEARCH_MCP_ENABLE_CRAWLER`, `RESEARCH_MCP_ALLOW_CUSTOM_PATHS`, `RESEARCH_MCP_REMOTE_MODE`) has no effect.
* **Arbitrary local file read through SQL (verified).** `analytics_sql` has no path controls, and the `dataset_query` sandbox can be bypassed. I verified with DuckDB 1.5 in a scratch venv that `read_text('<path>')`, `read_csv(['<path>'])` and `glob('/etc/*')` pass the read-only guard and return file contents. External access and extension auto-install are on by default. A prompt-injected model could read `~/.ssh`, `~/.aws`, or the MCP client config that holds every API key in plaintext.
* **Credential leaks.** `download_core_paper` sends `Authorization: Bearer <CORE_API_KEY>` to whatever third-party host CORE lists as the PDF location (server.py:2693-2698). Google and SerpAPI keys travel as URL query parameters, so `requests` connection errors echo them into tool output (server.py:2859, 3349).
* **HTTP mode has no authentication.** `RESEARCH_MCP_AUTH_TOKEN` is parsed in config.py but never checked. FastMCP 1.27 binds to loopback and turns on DNS-rebinding protection by default, so only local processes can reach it.
* **No monitoring exists.** There are no health checks, no per-source error or latency tracking, no quota visibility and no credential-expiry detection. Logs are unstructured stderr. Long tools block the event loop because FastMCP runs sync tools inline.
* **Upstream changes already affect v1.** The Google Custom Search JSON API (always appended as the last IAM fallback) shuts down on 2027-01-01, 74 days from today. Since February 2026 OpenAlex ignores `mailto` and requires a free API key, which v1 does not support. Brave dropped its free tier for metered billing, and v1 can turn one IAM query into up to 3 billed Brave calls.
* **Multiple processes.** Each MCP client (Claude Code, Claude desktop, OpenClaw) starts its own server process. Each has its own rate limiters (which breaks the arXiv one-request-per-3-seconds rule), they contend for the DuckDB embeddings file lock, and they share no health state. v2 should run one resident daemon under launchd, with thin stdio shims.

## 2. Credential inventory

Legend. Req: R = required for the listed tools, O = optional enhancement. "Detect" lists the cheapest reliable programmatic check; probes that cost quota are marked.

| Name | Kind | Used by tools (server.py lines) | Req | Missing behavior today | Invalid behavior today | Expires? | How to detect expiry or invalidity (v2) |
|---|---|---|---|---|---|---|---|
| `CORE_API_KEY` | Bearer API key (header) | `search_core`, `get_core_work`, `download_core_paper` (2502-2510, 2551-2733) | R | `get_core_work`/`download_core_paper` return `{"error":"CORE_API_KEY not set."}`. `search_core` sends the request unauthenticated, and `raise_for_status` throws an uncaught HTTP error into the tool result. | 401/403 raised as a raw exception; no classification. | No documented expiry (verify with CORE). | Passive: classify 401/403 as `invalid` and capture any rate-limit headers CORE returns. Active: one `GET /v3/search/works?q=test&limit=1` at most hourly, because the free tier allows about 10 req/min (README) and the server already waits 6.5 s between calls. Track a manual `rotate_by` date. |
| `GOOGLE_DEVKNOWLEDGE_API_KEY` | Google API key (query param `key=`) | `search_gcp_docs` (2757, 2819-2876); also reused as the Custom Search key by the google provider in `search_iam_docs` (3215-3233) | R for GCP docs; R for PSE path | Error JSON with a hint (2830-2836). For PSE, the `ValueError` is caught and the chain falls through. | GCP: returns `HTTP <code>` plus the first 500 chars of the Google error body to the model (2853-2857). Network errors return `str(e)`, which includes the full URL with `key=` (2859). | Google API keys do not expire by default. Google recommends periodic rotation and API restrictions. | Active probe: `GET v1/documents:searchDocumentChunks?query=iam&pageSize=1` using header `x-goog-api-key` (no known quota cost; run every 6 h). Classify 400 `API_KEY_INVALID` and 403 `SERVICE_DISABLED`/`API_KEY_SERVICE_BLOCKED` as `invalid`. Track `rotate_by` (for example, 180 days from the Keychain item modification date). **Move the key from the query string to the `x-goog-api-key` header**, as Google advises. |
| `GOOGLE_PSE_CX` | Identifier (not secret) | `search_iam_docs` google provider (3050, 3215-3233) | R for PSE | `ValueError` caught; the provider is skipped. | 400 from Google, surfaced in `details`. | **Service deprecation:** the Custom Search JSON API no longer accepts new customers and shuts down on 2027-01-01. | Report as source state `deprecated (days_to_shutdown)` starting now. The probe uses one query from the 100/day free allowance, so run it daily at most. Plan removal before 2027-01-01. |
| `SERPAPI_API_KEY` | API key (query param `api_key=`) | `search_iam_docs` serpapi provider (3052, 3198-3212) | O | Provider skipped in `auto` mode. | HTTP error caught; `details` carries the body. A connection error string includes the URL with `api_key=` (3349). | Keys do not expire; the plan renews monthly. | **Free Account API:** `GET https://serpapi.com/account.json` (the key goes in a param, so redact it from errors). It returns `plan_searches_left`, `total_searches_left`, `this_month_usage`, `plan_renewal_date` and `account_rate_limit_per_hour`, and calls are not billed. Use it for `invalid` (error) and `quota_low` (for example, below 10% of `searches_per_month`). Run every 6 h. |
| `BRAVE_SEARCH_API_KEY` | API key (header `X-Subscription-Token`) | `search_iam_docs` brave provider (3053, 3147-3195) | O | Provider skipped in `auto` mode. | HTTP error caught per batch; the first error is re-raised. | Key does not expire. **Billing changed:** the free tier was removed; plans now include $5 of monthly credit (about 1,000 queries), and the card is charged beyond that. | **Passive, no cost:** every response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` and `X-RateLimit-Policy` (per-second and monthly windows). Store the monthly remaining value and derive `quota_low`. A 429 means a limit was hit. An active probe costs a billed query, so run it at most daily and only if no real call happened in 24 h. Cap fan-out (3 calls per IAM query today, 3175-3180). |
| `VERTEX_AI_PROJECT`, `VERTEX_AI_LOCATION`, `VERTEX_AI_IAM_ENGINE_ID` | Config identifiers (not secret) | `search_iam_docs` vertex provider (3056-3108) | O | `ValueError`; provider skipped. | 404/403 surfaced in `details`. | n/a | Check them during the daily ADC probe by calling the engine with `pageSize=1`. One secondary source reports that Vertex AI Search has been renamed Agent Search; verify the endpoint before relying on it. |
| Google ADC via `google.auth.default()` (reads `GOOGLE_APPLICATION_CREDENTIALS` or `~/.config/gcloud/application_default_credentials.json`, plus `GOOGLE_CLOUD_PROJECT`) | OAuth refresh token (user ADC) or service account key file | vertex provider (3062-3078) | O | `DefaultCredentialsError` caught as a generic `last_error` string. | `RefreshError` (for example, `invalid_grant` or a reauthentication requirement) caught as a generic string. | **User ADC:** Google says local ADC credentials expire when the Workspace session expires, and refresh tokens can also expire for other reasons; the fix is `gcloud auth application-default login`. **SA keys:** user-managed keys never expire unless the org policy `iam.serviceAccountKeyExpiryHours` (8 to 2160 h) applies or the key was uploaded with a certificate (`validBeforeTime`). | Active probe: `creds.refresh(Request())` daily (no API quota). Map a `RefreshError` containing `invalid_grant` or `reauth` to `invalid`, with the fix text "run gcloud auth application-default login". For an SA key file, read `validBeforeTime` through IAM `keys.get` if permitted; otherwise track key age from file metadata and warn at 90 days. Note that the ADC file is a plaintext refresh token on disk (see OPS-24). |
| `GITHUB_TOKEN` | PAT (classic or fine-grained), Bearer header | `search_github_repos` (O), `search_github_code` (R), `fetch_github_readme` (O) (3620-3780) | R for code search | Code search returns an error with a hint; the other two run unauthenticated at 60 req/h. | `str(e)` returned ("401 Client Error ..."); no classification. | Yes, when the token was created with an expiry date; GitHub revokes it on that date. GitHub also revokes PATs pushed to public repos or unused for a year. | **Passive:** responses to PAT-authenticated calls carry `GitHub-Authentication-Token-Expiration` (absent means no expiry). Parse it on every call and store `expires_at`. **Active, free:** `GET /rate_limit` doesn't count against the limit. It checks the token (401 means `invalid`) and reports `core`, `search` and `code_search` remaining for `quota_low`. Run hourly. |
| `RESEARCH_MCP_AUTH_TOKEN` | Locally generated bearer token for HTTP mode | Parsed in config.py:32, 49-50, 75; **never checked by server.py** | R for non-loopback HTTP (by design) | Nothing happens; HTTP runs open (OPS-07). | n/a | Local secret; no external expiry. | In v2, generate it at install, store it in Keychain, rotate it on demand from the UI, and record `created_at` (warn at 180 days). |
| `UNPAYWALL_EMAIL` | Contact identifier (PII, not secret) | `download_paper_by_doi` (1611, 1897-1922, 1965); adapter User-Agent (4199-4201) | O | The default `research-mcp@example.com` silently disables the Unpaywall source (1898). | Unpaywall rejects or limits invalid emails. | n/a | Config check: report `unconfigured` when unset or containing `example.com`. Probe one known DOI daily. |
| `OPENALEX_EMAIL` | Contact identifier | OpenAlex tools via `mailto` param (2016-2023), adapter User-Agent | O | Requests go without `mailto`. | n/a | **Obsolete:** OpenAlex says the `mailto` polite pool ended in February 2026 and was replaced by API keys; `mailto` is now ignored. | Retire it and add `OPENALEX_API_KEY` (below). |
| `OPENALEX_API_KEY` (**new, not read by v1**) | API key | All OpenAlex tools; `check_retractions` OpenAlex signal | R (OpenAlex says an API key is needed "for all requests") | v1 runs without a key, which OpenAlex describes as demonstration-only. | n/a | Free key with a daily usage budget (about $1/day of credit per a secondary source; single-record lookups free). | Probe one free single-record lookup daily. Watch for 401/429 and any usage headers (not documented in the sources found; verify). Show budget status as `unknown` until verified. |
| `SEMANTIC_SCHOLAR_API_KEY` (**suggested, not read by v1**) | API key (`x-api-key` header) | `search_semantic_scholar`, `get_semantic_scholar_paper`, DOI fallback | O | v1 uses the shared unauthenticated pool and retries 429s with sleeps (996-1009). | n/a | Not documented. | With a key: probe a single paper daily and classify 403 as `invalid`. Without one: track the passive 429 rate as `degraded`. |
| Implicit env read by libraries | `FASTMCP_*` (FastMCP settings), `HTTPS_PROXY`/`REQUESTS_CA_BUNDLE` (requests), `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT` | n/a | n/a | n/a | n/a | n/a | Show them on the UI Settings page (names and whether set, never values). |

Non-secret config env vars (inventory only): `ARXIV_DOWNLOAD_DIR`, `ARXIV_DB_PATH`, `ARXIV_CHUNK_SIZE`, `ARXIV_CHUNK_OVERLAP`, `IAM_DOCS_SEARCH_PROVIDER`, `DUCKDB_DATASETS_DIR`, `EMBED_MODEL_NAME`, `EMBED_DIM`, `EMBED_DB_PATH`, and the unused `RESEARCH_MCP_*` set in config.py (`DATA_ROOT`, `DATASET_ROOT`, `REMOTE_MODE`, `ENABLE_EXPERT_SQL`, `ENABLE_CRAWLER`, `ALLOW_CUSTOM_PATHS`, `MAX_RESPONSE_BYTES`, `MAX_DOWNLOAD_BYTES`, `HOST`, `PORT`). v1 has two competing config systems (`ARXIV_*` in server.py and `RESEARCH_MCP_*` in config.py); v2 should have one.

Sources that need no credential but still need health probes: arXiv, Semantic Scholar (without a key), MIT DSpace, Harvard DASH, Cornell eCommons, Penn ScholarlyCommons, Crossref, DataCite, OSF/SHARE, PsyArXiv, AWS docs search proxy, Microsoft Learn search, Europe PMC, Crossref updates (retractions), OpenCitations, ClinicalTrials.gov, and the 6 IAM crawl targets.

## 3. Secret handling today

* **Source of secrets:** process environment only. There is no `.env` loader, although `.gitignore` excludes `.env`. The README tells users to paste keys into the client config `env` block (README.md:254-266). On this Mac that means plaintext keys in `~/Library/Application Support/Claude/claude_desktop_config.json`, another copy in Claude Code's config if added with `claude mcp add -e`, and another in OpenClaw's config. That makes three plaintext copies. Any process running as the user can read them, including through the SQL file-read hole (OPS-01).
* **Echo risks:**
  * Google and SerpAPI keys are URL query parameters (2838-2844, 3201-3210, 3220-3229). `requests`/urllib3 connection errors include the full URL with its query, and v1 returns `str(e)` to the model (2859, 3349), so the keys end up in chat transcripts.
  * Upstream error bodies are returned raw (2856, 3345-3347).
  * The CORE bearer token is sent to non-CORE hosts (OPS-03).
* **Logging:** no secret is logged directly. Logs do record full query params (692, 1769, 2159), including the OpenAlex `mailto` email, and exception strings at DEBUG and WARNING that can contain URLs.
* **Redaction:** none. `ScopedCredential` in security.py:140-151 (headers scoped to one origin) is the right building block, but nothing uses it.
* **File permissions:** directories are created with the default umask (`mkdir(parents=True)` at 80, 625, 4024), so PDFs and DBs are world-readable under the typical 022 umask. That matters little on a single-user Mac. gcloud creates the ADC file as 0600.

**Recommendation (v2): Keychain-backed loading, no plaintext on disk.**

1. Store each secret as a generic password with service name `research-mcp/<NAME>` (for example `research-mcp/CORE_API_KEY`) and account set to the macOS user. Read it with the owner's existing resolver convention, the `keyring` package (macOS backend), or `security find-generic-password -s <service> -w` as a subprocess.
2. The v2 config file `~/.config/research-mcp/config.toml` holds only references, for example `core.api_key = "keychain:research-mcp/CORE_API_KEY"`. Client configs contain no `env` secrets; they launch `research-mcp stdio`, which connects to the daemon.
3. Wrap values in a `Secret` type whose `__repr__`/`__str__` return `Secret(name=..., fp=ab12)`. Only the HTTP client layer calls `.reveal()`.
4. Read secrets once at daemon start and keep them in memory. Re-read on `SIGHUP` or a UI "reload credentials" action, so rotating a key needs no restart.
5. Keychain caveat: access is granted per binary path. Run the daemon from a stable venv interpreter path and expect one "Always Allow" prompt per item after Python upgrades. The launchd agent runs in the user's GUI session, so it can reach the login keychain.
6. Store credential metadata, never values, in `state.db`: name, source (keychain or env), fingerprint (first 8 hex of SHA-256 of the value, to notice rotations), Keychain modification date, `expires_at` (from headers or manual entry), `rotate_by`, `last_validated_at`, `last_result`, `status`.
7. Use one global redaction filter on log records and on every error string returned to a tool. It masks known secret values, `key=`, `api_key=`, `token=`, `Authorization:`, `X-Subscription-Token:`, `x-goog-api-key:`, and the prefixes `AIza`, `ghp_` and `github_pat_`.
8. A secret scan in CI is still worth having (gitleaks or trufflehog on push).

## 4. Findings

Severity scale: Critical (exploitable now with high impact), High, Medium, Low, Info.

| ID | Sev | Area | Evidence (file:line) | Issue | Recommendation |
|---|---|---|---|---|---|
| OPS-01 | Critical | SQL / file read | server.py:3783-3796 (shared DuckDB, external access on), 3813-3821 (regex guard), 3835-3873 (`analytics_sql`) | `analytics_sql` has no path controls. Verified: `SELECT content FROM read_text('<file>')`, `SELECT * FROM read_csv(['<file>'], header=false)` and `SELECT * FROM glob('/etc/*')` all pass `_ensure_read_only_sql` and return data. `enable_external_access`, `autoload_known_extensions` and `autoinstall_known_extensions` are all true, so URL reads (`read_csv('https://...')`) can download extensions and make outbound requests. Any fetched document can trigger this through prompt injection. Targets include the client config files that hold API keys. | v2: drop free-form SQL from MCP by default (expert flag, off). Where it stays, use a dedicated DuckDB connection. Attach the index read-only, then set `enable_external_access=false`, `allowed_directories=[dataset_root]`, `autoload_known_extensions=false`, `autoinstall_known_extensions=false`, `memory_limit` and `threads`, then `lock_configuration=true`. Preinstall the needed extensions at install time. Prefer parameterized, purpose-built query tools over raw SQL. |
| OPS-02 | High | SQL sandbox bypass | server.py:3939-3965 | The `dataset_query` sandbox checks a path only when it is a quoted string directly after a named reader function. Verified bypasses: list syntax `read_csv(['/etc/passwd'])` (the regex sees nothing), `read_text`/`read_blob`, `glob`, and bare file names in FROM (`FROM '<file>'`). Its string-replace rewrite can also corrupt queries. | Same DuckDB hardening as OPS-01. Never sandbox SQL with regex. |
| OPS-03 | High | Credential exfiltration | server.py:2681-2698 | `download_core_paper` downloads `download_url` or `fulltext_urls[0]` (third-party repository hosts taken from CORE metadata) with `headers=_core_headers()`. That sends `Authorization: Bearer <CORE_API_KEY>` to arbitrary hosts. | Attach credentials only when the origin matches (`security.credential_headers_for_url` with `ScopedCredential("https://api.core.ac.uk")`). Download through `download_pdf_atomic`. |
| OPS-04 | High | Secret echo | server.py:2838-2859, 3201-3229, 3343-3349 | Google and SerpAPI keys travel in URL query strings. `requests` connection and timeout exceptions include the URL and its query, and v1 returns `f"{e}"` to the model. Raw upstream error bodies are also returned. | Send the Google key in the `x-goog-api-key` header, as Google's guidance says. SerpAPI only takes the key as a query param, so redact it before any string leaves the HTTP layer. Return a classified error code (`AUTH_REQUIRED`, `RATE_LIMITED`, `UPSTREAM_ERROR` from errors.py) plus a correlation id, and keep details in redacted logs. |
| OPS-05 | High | SSRF / unbounded download | server.py:748-755 (arXiv), 1961-1977 (DOI via Unpaywall or Semantic Scholar URL), 2690-2708 (CORE) | Three download paths use plain `requests.get(..., stream=True)`. That follows redirects to any host, allows http, doesn't block private or link-local IPs, has no size cap and no content-type or `%PDF-` check, and writes straight into the final path, leaving partial files on failure. The PDF URLs come from third-party metadata. `security.download_pdf_atomic` already handles all of this but is unused. | Route every download through `download_pdf_atomic` with a per-source host allowlist (or a public-IP-only policy for open-access hosts), `max_bytes`, a redirect cap that rechecks each hop, and a magic-byte check. Downloads land only in the cache directory. |
| OPS-06 | High | Dead safety layer | server.py:4191-4196 (only imports); config.py:17-76; security.py; cache.py; jobs.py; tests/test_modern_mcp.py:14-28 and tests/test_research_workflows.py:12-22 (module-level skip) | The server doesn't use `Settings` (loopback/auth policy, expert SQL and path flags, PDF page and byte caps), `security.py`, `SemanticCache` or `JobService`. Their own tests pass or skip, so CI is green while none of these controls run in production. The env flags give a false sense of control. | v2 builds the server from these modules through an app factory. Add a test asserting that every tool resolves `Settings` and uses the shared HTTP client. Make the skipped contract tests fail CI once their target module exists. |
| OPS-07 | High | HTTP auth | server.py:4597-4613; config.py:49-50, 75 | `--transport sse` starts with no authentication, and `RESEARCH_MCP_AUTH_TOKEN` is never checked. FastMCP 1.27 defaults (host 127.0.0.1, DNS-rebinding protection with Host/Origin allowlists) block remote and browser access, but any local process can call every tool, including OPS-01. SSE is also deprecated in favor of streamable HTTP. | v2 daemon: streamable HTTP on 127.0.0.1 only, with a bearer token from Keychain required on every request (constant-time compare). Refuse to start on a non-loopback host, and keep the Host/Origin checks. |
| OPS-08 | High | Path control | server.py:623-626 (`_get_download_dir`), 716-773 (`download_paper` `download_dir`), 776-825 (`index_paper` `pdf_path`), 828-884 (`index_all_papers` `download_dir`), 1838-2006, 2645-2733 | The model can pick any directory to create and write into, and any file to parse. `index_paper(pdf_path=...)` opens any readable file with PyMuPDF (which reads many formats) and stores the text, and `get_paper_text` then returns it. The CORE file name embeds the raw `core_id`. | Remove caller-selected paths from MCP tools. All writes go to the cache root through `resolve_confined_path`. Validate IDs with a regex per source (arXiv, DOI, numeric CORE id). |
| OPS-09 | Medium | URL fetch controls | server.py:2923-2978 (`fetch_cloud_doc_page`), 3388-3436, 3478-3489 (crawler) | The host allowlist is checked once and redirects are followed unchecked. http is allowed. The whole body is read into memory (`resp.text`) before truncation. The crawler's `path_filters` match any substring, so `https://evil.example/?x=developer.hashicorp.com/vault/docs` passes. Sitemap and nested sitemap URLs (3409) are fetched without host checks or a User-Agent. robots.txt is ignored. | Use one `SafeHTTPClient`: https only, `allow_redirects=False` with a recheck on every hop, a per-source host allowlist matched on the parsed hostname, a streamed byte cap, and timeouts. Crawler filters match hostname plus path prefix. Make the `ENABLE_CRAWLER` flag actually gate the crawler. |
| OPS-10 | Medium | Prompt injection exposure | server.py:930-949 (`get_paper_text`), 2924-2978, 3736-3768 (`fetch_github_readme`), 3526-3575; models.py:80 | Untrusted text (PDF bodies, doc pages, READMEs, search snippets, upstream error bodies) goes back raw. Legacy tools mark nothing as untrusted; only the adapters' `Provenance.untrusted_content` exists. No tool sets MCP annotations (`readOnlyHint`, `destructiveHint`, `openWorldHint`; 0 occurrences), so clients can't tell tools that change state (`remove_paper`, downloads, indexing, `embed_chunks`) from read-only ones. Together with OPS-01 and OPS-08, injected text can steer a model into reading files. | Wrap fetched content in a fixed envelope (`{"untrusted": true, "source": ..., "content": ...}`) and add a server instruction to treat it as data. Set tool annotations. Keep destructive and maintenance actions out of MCP or require confirmation tokens (see the cache review design in 5.8). Cap response bytes per tool (`Settings.max_response_bytes`). |
| OPS-11 | Medium | Secret storage | README.md:254-266; config.py:75 | Secrets sit as plaintext in client JSON configs, in several copies. There is no rotation workflow. | Keychain-backed loading (section 3). Client configs carry no secrets. |
| OPS-12 | Medium | Process model | server.py:614-620, 535-545, 3783-3796, 4020-4027 | Each MCP client starts its own process. (a) Rate limiters live in memory per process, so concurrent clients break arXiv's 1-request-per-3-seconds rule and CORE's per-minute budget. (b) DuckDB allows one read-write process per database file, so `embeddings.duckdb` (attached read-write at 4025) fails with a lock error in the second client. (c) The embedding model loads in every process. (d) No health, job or quota state can be shared. | v2 runs one resident daemon (launchd LaunchAgent, KeepAlive) that owns the HTTP clients, rate limiters, DBs, scheduler and UI. MCP clients launch `research-mcp stdio`, a thin shim that relays stdio to the daemon's loopback endpoint and asks launchd to start the daemon if it is down. Clients that support streamable HTTP can connect directly. |
| OPS-13 | Medium | Blocking and long tasks | mcp 1.27 `func_metadata.call_fn_with_arg_validation` calls sync tools inline; server.py:828-884, 3441-3522 (up to 500 pages with 0.2 s sleeps), 4069-4120 (up to 10,000 chunks), 996-1009 (sleeps up to 30 s), 4343-4560 (async tools calling sync `requests`) | Sync tools run on the event loop, so one slow tool stalls all MCP traffic in that process. Long jobs have no progress reporting, cancellation or resume, and they exceed client tool timeouts. `JobService` exists but is unused. | Async HTTP (httpx) with a concurrency limit per source. Long operations become jobs (`JobService`, persisted to `state.db`) that return a `job_id`, report progress and can be cancelled. CPU-heavy work (PDF parsing, embedding) runs in a worker process pool. |
| OPS-14 | Medium | Logging | server.py:60-61, 692, 1769, 2159, 648, 874 | `basicConfig` writes INFO text to stderr with f-strings. Logs include full query params and the contact email. There are no request or correlation ids (errors.py has `correlation_id`, unused), no duration, source, status or bytes fields, and no dedicated log file or rotation. Many failures log only at DEBUG (813, 862, 1424, 3413, 3429). | JSON-lines logs with a redaction filter and rotation (section 5.6). |
| OPS-15 | Medium | Monitoring | whole server | No health or readiness checks, no metrics, no per-source error rate, latency or quota tracking, and no credential-expiry detection. Undocumented endpoints can fail silently: the AWS docs search proxy (2757-2815) and the Microsoft Learn site-search API (2879-2920) can change their response format and return 200 with no results, which v1 reports as "0 results". | Source registry with passive telemetry plus active test queries that also check the response format (section 5.3). |
| OPS-16 | Medium | Upstream changes | server.py:3256 (google always appended), 2016-2023, 3172-3180 | The Google Custom Search JSON API shuts down on 2027-01-01. OpenAlex replaced the `mailto` polite pool with mandatory free API keys (February 2026). Brave is now metered at about $5 per 1,000 queries beyond the $5 monthly credit, and v1 sends up to 3 Brave calls per IAM query. | Add a `deprecated` source state with a countdown. Add `OPENALEX_API_KEY`. Add spend and budget caps per provider, with Brave fan-out limited to 1 call by default. Re-evaluate the IAM provider chain (Vertex, Brave, SerpAPI) before the PSE shutdown. |
| OPS-17 | Medium | Embedding store integrity | server.py:4027 (`hnsw_enable_experimental_persistence=true`), 166-170 and 210-214 (re-index deletes chunks; new chunk_ids), 4048-4066 | DuckDB warns that a persisted HNSW index can lose data or become corrupt after an unclean shutdown (WAL recovery isn't implemented for custom indexes) and advises against production use. Re-indexing and `remove_paper` leave orphan embeddings keyed to dead chunk_ids, so `embedding_stats.missing` (total minus embedded) is wrong. | Treat embeddings as a rebuildable cache. Key them by `(document_id, chunk_index, content_hash)` and delete them in the same job as the chunks. Build the HNSW index in memory at daemon start instead of persisting it (or check and rebuild it on start). Add a reconcile check (5.9). |
| OPS-18 | Medium | Cache lifecycle, disk, integrity | server.py:87-145 (schema; `OperationalError` swallowed at 144-145), 718-773, 940-976 | No retention, no disk-usage visibility, no check that `pdf_path` files still exist, no `PRAGMA quick_check` or FTS5 `integrity-check`. The schema is created ad hoc with no version number (repository.py has `user_version` migrations, but server.py doesn't use them). `remove_paper` leaves PDFs on disk. | Implement the 30-day retention lifecycle with owner review (5.8), disk monitoring (5.8.6) and integrity checks (5.9). Run schema migrations through `PRAGMA user_version`. |
| OPS-19 | Low | Transport | server.py:42 | The arXiv API base is `http://export.arxiv.org`: plaintext and open to tampering. | Use https. |
| OPS-20 | Low | PDF parsing | server.py:445-453, 523-529 | PyMuPDF (the MuPDF C library) parses untrusted PDFs inside the server process with no page cap (`Settings.max_pdf_pages` unused), no time or memory limit, and no isolation. A malformed or hostile PDF can hang or crash the server. | Parse in a subprocess worker with `resource` limits (CPU seconds, address space), a wall-clock timeout and a page cap. Keep PyMuPDF updated and track MuPDF advisories in the dependency audit job. |
| OPS-21 | Low | Response bounds | research_mcp/adapters/base.py:104-118; many `resp.json()`/`resp.text` calls in server.py | The adapter byte limit is checked only after the whole body has been read. Legacy tools have no response-size caps, and some tool outputs are very large (`get_paper_text` returns a whole paper). | Stream with a byte cap in the shared client. Paginate large tool outputs with cursors. |
| OPS-22 | Low | Build and CI hygiene | pyproject.toml:81-95; .github/workflows/ci.yml:1-31; Makefile:21-25 | Dependency versions are open ranges with no lockfile. There's no dependency audit (pip-audit or OSV), no Dependabot or Renovate, and no secret scanning. Actions are pinned by tag rather than SHA, there's no `permissions:` block, and no macOS runner even though production runs on macOS. The package already claims version 2.0.0. | Use a uv lockfile and add macos-latest to the CI matrix. Add a weekly pip-audit, Dependabot for pip and actions, a gitleaks step and `permissions: contents: read`. Version v2 as 3.0.0 or reset the numbering. |
| OPS-23 | Low | Rate limiting and cost | server.py:535-545, 996-1009, 3178 | Rate limiting is fixed sleeps per process. `Retry-After` is honored only for DSpace. There are no budgets for metered providers (Brave, SerpAPI, OpenAlex usage). | Per-source token buckets in the daemon, `Retry-After` honored everywhere, and daily and monthly budget caps with `quota_low` alerts. |
| OPS-24 | Low | Google ADC on disk | server.py:3062-3078 | If Vertex is used, the gcloud ADC file stores a refresh token in plaintext (0600). Refresh failures come back as an opaque string. | Accept the gcloud-managed file (0600) or drop the Vertex provider. Classify `RefreshError` and send a notification with the exact fix command. |
| OPS-25 | Info | Positives | server.py:285-334 (FTS5 quoting and fallback), 171-208 (parameterized SQL), 1206-1208 and 1370-1378 (DSpace UUID validation); security.py (well tested) | User input to FTS is safely quoted, and index SQL is parameterized. security.py is a good base for v2. FastMCP's defaults (loopback, DNS-rebinding protection) are sensible. | Reuse them. |

## 5. v2 operations design

### 5.1 Process model

* **`research-mcpd`** is one resident Python process started by a launchd LaunchAgent (`RunAtLoad`, `KeepAlive`). It hosts:
  * core services (source adapters, safe HTTP client, rate limiters, cache, jobs)
  * the scheduler
  * `state.db` (SQLite: credential metadata, source health, call telemetry, jobs, cache lifecycle, archive catalog, notifications)
  * the MCP streamable HTTP endpoint and the web UI, both on `127.0.0.1:<port>` (Starlette, which FastMCP already depends on)
* **`research-mcp stdio`** is what Claude desktop, Claude Code and OpenClaw launch. It relays stdio to the daemon, using the bearer token from Keychain. If the daemon is down it runs `launchctl kickstart` and retries. If that also fails, it returns one clear MCP error: "research daemon not running; see UI or run research-mcp doctor".
* **`research-mcp doctor [--notify] [--json]`** is a CLI that runs every check without the daemon. The launchd watchdog uses it too.
* **Data layout:**

| Path | Contents |
|---|---|
| `~/.config/research-mcp/config.toml` | Settings and secret references |
| `~/Library/Application Support/research-mcp/state.db` | Small; backed up |
| `~/Library/Caches/research-mcp/` | Cache: index.db, PDFs, embeddings (rebuildable) |
| `~/Library/Logs/research-mcp/` | Logs |
| `~/arxiv-papers` | Moved into the cache on first run |

### 5.2 Source registry (horizontal reach is the product)

Every source is declared once, with:

* `id`, `display_name`, `category` (papers, repositories, doi, docs, iam, code, biomedical)
* `tools` that use it
* `credential_refs` (zero or more)
* `probe` (callable, cost class, cadence)
* `quota_signal` (none, headers, account endpoint, derived)
* `rate_policy` (token bucket)
* `expected_shape` (checks the test query's response must pass)
* `docs_url` and `status_note` (for deprecations)

Initial registry (27 sources) and probe plan:

| Source | Credential | Test query (cheap) | Cadence | Quota signal |
|---|---|---|---|---|
| arXiv API | none | `id_list=<known id>&max_results=1`, expect 1 entry | 60 min | none; keep the 3 s spacing across all clients |
| Semantic Scholar | optional key | `/paper/<known DOI>?fields=title` | 60 min | 429 rate (passive) |
| MIT DSpace, Harvard DASH, Cornell eCommons, Penn ScholarlyCommons | none | `discover/search/objects?query=test&size=1`, expect `_embedded` | 60 min each | 429 plus Retry-After |
| Crossref | none (polite UA) | `/works/<known DOI>` | 60 min | 429 |
| DataCite | none | `/dois/<known DOI>` | 6 h | 429 |
| Unpaywall | email | `/v2/<known DOI>?email=` | 6 h | 429 |
| OpenAlex | API key | single work by DOI (free per OpenAlex pricing) | 60 min | 401/429; usage headers if any (verify) |
| OSF/SHARE, PsyArXiv | none | search `q=test` size 1 | 6 h | 429 |
| CORE | CORE_API_KEY | `search/works?q=test&limit=1` | 60 min | 429; rate-limit headers if present |
| AWS docs proxy (undocumented) | none | query "IAM policy", expect at least 1 result linking to docs.aws.amazon.com | 60 min | n/a; a changed response format means `down` |
| GCP Developer Knowledge | GOOGLE_DEVKNOWLEDGE_API_KEY | `searchDocumentChunks pageSize=1` | 6 h | 429/403 quota |
| Microsoft Learn search (undocumented) | none | query "Entra ID", expect results | 60 min | a changed response format means `down` |
| IAM: Vertex | ADC | refresh plus `pageSize=1` | 24 h | quota errors |
| IAM: Brave | BRAVE_SEARCH_API_KEY | passive headers; active only if no calls in 24 h | 24 h | monthly `X-RateLimit-Remaining` |
| IAM: SerpAPI | SERPAPI_API_KEY | `account.json` (free) | 6 h | `plan_searches_left`, `total_searches_left` |
| IAM: Google PSE | key plus CX | one query (uses the free 100/day) | 24 h | `deprecated` until 2027-01-01, then `retired` |
| IAM crawl targets (6) | none | HEAD or GET the sitemap or seed page, expect 200 and XML or HTML | 24 h | n/a |
| GitHub | GITHUB_TOKEN | `GET /rate_limit` (free) | 60 min | `resources.core/search/code_search.remaining`; expiry header |
| Europe PMC | none | search `query=test&pageSize=1` | 60 min | 429 |
| Crossref updates (retractions) | none | a known retracted DOI, expect the update to be present | 24 h | 429 |
| OpenCitations | none | known DOI | 6 h | 429 |
| ClinicalTrials.gov | none | `query.term=test&pageSize=1` | 6 h | 429 |
| Local: cache index, embeddings, archive folder, disk | n/a | see 5.8 and 5.9 | 15 min to 24 h | free disk |

Probe start times are randomized slightly, probes go through the same rate limiter as user traffic, and a probe is skipped when a real call in the same window already showed the source working. Using passive evidence first saves quota.

### 5.3 Health and credential status model

**Credential status** (one row per credential):

| State | Rule |
|---|---|
| `ok` | Checked within its cadence; no expiry, or expiry more than 14 days away. |
| `expiring_soon(days)` | `expires_at` within 14 days (warning) or 3 days or less (critical). Taken from the GitHub header, the SA key `validBeforeTime`, or a manual `rotate_by`. |
| `invalid` | The last probe or call failed authentication (401; 403 with an auth reason; `RefreshError` with `invalid_grant` or reauth; Google `API_KEY_INVALID`). |
| `missing` | Referenced but not found in Keychain or env. |
| `quota_low(pct)` | Less than 10% of the period allowance remains (SerpAPI account, Brave monthly header, GitHub `/rate_limit`, budget caps). |
| `unknown_expiry` | Valid, but the provider doesn't expose an expiry; shows the key's age and `rotate_by` instead. |

**Source status** (what the source board shows); the worst state wins:

| State | Rule |
|---|---|
| `unconfigured` | A required credential is missing. Shown in neutral grey, not red, so optional sources don't create noise. |
| `down` | 3 failed probes in a row; or every call failed over at least 5 calls in 15 min; or the test query's response failed its format check (undocumented endpoints). |
| `credential_invalid` | A required credential is `invalid`. |
| `degraded` | Error rate above 10% over the last 20 calls; or p95 latency above 3x its 7-day baseline; or recent 429s; or `quota_low`. |
| `credential_expiring(days)` | A credential is `expiring_soon`. |
| `deprecated(days)` | The provider has announced a shutdown date (Google PSE: 2027-01-01). |
| `ok` | Otherwise. |

Each source row shows: status, the reason with a fix hint, last probe time and result, calls in the last 24 h, error rate, p50/p95 latency, last error code (classified and redacted), quota remaining and reset, and credential badges.

**Telemetry:** one HTTP client wrapper writes a row per outbound call to `state.db.calls`: ts, source, op, status_code, error_code, latency_ms, bytes, parsed rate-limit headers, parsed token-expiry header and correlation_id. Raw rows are kept 30 days, with hourly rollups kept 13 months.

### 5.4 Scheduling (launchd plus in-daemon)

* **An asyncio scheduler inside the daemon** runs the probes (table above), cache lifecycle checks, disk checks and rollups. The daemon is always running, so this covers nearly all scheduling.
* **launchd LaunchAgents** (in `~/Library/LaunchAgents/`):
  1. `com.kennyhill.research-mcpd.plist`: `ProgramArguments` = venv python `-m research_mcp.daemon`, `RunAtLoad` true, `KeepAlive` true, `ThrottleInterval` 30, `StandardErrorPath` in the log directory, `ProcessType` Background.
  2. `com.kennyhill.research-mcp-doctor.plist`: runs `research-mcp doctor --notify` with `StartCalendarInterval` Hour 8 Minute 52 (offset from the hour on purpose). This is an independent watchdog. It checks that the daemon answers `/healthz`, re-checks credentials directly from Keychain, and sends notifications even if the daemon is dead. If the Mac was asleep at the scheduled time, launchd runs the job once after it wakes.
  3. Optional `com.kennyhill.research-mcp-maint.plist`: weekly on Sunday at 09:07 for the dependency audit (`pip-audit` against the lockfile), `VACUUM`/`ANALYZE` and FTS optimize.
* The daemon runs the daily cache expiry review at 09:00 local time. The doctor job repeats it if the daemon missed it.

### 5.5 Notifications

| Channel | Use | Notes |
|---|---|---|
| macOS notification | Primary | `terminal-notifier` (Homebrew), so a click opens the matching UI page (`-open http://127.0.0.1:<port>/sources#github`). Fallback: `osascript -e 'display notification ...'` (no click-through). Titles never contain secret values. |
| Agent inbox (OpenClaw or other) | Secondary, configurable | Write a JSON message to a configured inbox (OpenClaw webhook URL or inbox directory) with `type`, `severity`, `summary`, `ui_url` and `actions`. Also available to any MCP client as the resource `research://status` and the tool `ops_status`, so an agent can mention "GitHub token expires in 5 days" in chat. |
| UI banner | Always | Stays until resolved or acknowledged. |

Notification policy:

* Notify only when something changes state: a source goes `down`, a credential becomes `invalid`, `expiring_soon` (at 14, 7, 3 and 1 days), `quota_low` or `deprecated` (at 60, 30 and 7 days), a disk warning, the archive folder becomes unavailable, or a cache review batch is ready.
* Anything still unresolved goes into one daily digest instead of repeating.
* Quiet hours are configurable (default 21:00 to 08:00). Critical items wait for the morning digest, unless a credential used in the last hour became `invalid`.
* Every notification is stored in `state.db.notifications` with an acknowledged flag.

### 5.6 Structured logs

* JSON lines go to `~/Library/Logs/research-mcp/research-mcp.jsonl` via `RotatingFileHandler` (10 MB x 5). stderr gets WARNING and above only, so the stdio shim stays quiet.
* Fields: `ts`, `level`, `event`, `correlation_id`, `tool`, `source`, `op`, `status`, `error_code`, `latency_ms`, `bytes`, `cache` (hit/miss), `job_id`, `attempt`.
* Query text is logged only as a hash plus length by default; a debug flag includes it.
* The redaction filter from section 3 runs on every record and on every error returned to a tool.
* Error responses to MCP carry only `{code, message, retryable, correlation_id}` (errors.py already defines this). The UI log view can look up a correlation id.

### 5.7 Status and metrics endpoints (loopback only)

| Endpoint | Auth | Content |
|---|---|---|
| `GET /healthz` | none (loopback) | Liveness: `{"status":"ok","version":...}` |
| `GET /readyz` | none (loopback) | DB open, scheduler alive, Keychain readable |
| `GET /api/status` | bearer token or UI session | Full JSON: sources, credentials (no values), quotas, jobs, cache stats, disk, archive target health, last notifications |
| `GET /metrics` | bearer token | Optional Prometheus text: per-source request, error and latency histograms, quota gauges, cache bytes, job counts |
| MCP resource `research://status` | MCP session | Compact status for agents |

### 5.8 Cache lifecycle and archive (owner decisions)

**5.8.1 Item model.** Each cached item (a PDF with its chunks and embeddings, or a set of crawled doc pages) has: `item_id`, `source`, `source_id`, title, citation (CSL-JSON), `original_url`, `fetched_at`, `last_accessed_at`, `size_bytes`, `pinned`, `state`, `expires_at`, `review_batch_id` and `reask_count`. `expires_at` is `fetched_at` + 30 days. A sliding version (`last_accessed_at` + 30 days) is possible if the owner prefers it, but I recommend the fixed date because it is simpler and predictable.

**5.8.2 States.**

| State | Meaning | Next |
|---|---|---|
| `cached` | Active | Becomes `expiring` 3 days before `expires_at` |
| `pinned` | Owner pinned it | Never expires; unpinning returns it to `cached` with a fresh 30 days |
| `expiring` | In a review batch, awaiting a decision | `archived`, `discarded` or `kept` |
| `kept` | Unanswered, or "keep for now" | Asked again after 7 days; `expires_at` extended 7 days |
| `archived` | Copied to the archive and removed from the cache | Final; metadata and citation stay in the catalog |
| `discarded` | Owner chose to let it go | Files go to the cache trash for 7 days (undo possible), then are removed; the catalog keeps a record (title, citation, URL, discarded_at) |

**5.8.3 Daily expiry check (09:00).** The check picks items whose `expires_at` is within 3 days, plus `kept` items due to be asked again. It groups them into one batch with a `batch_id` and sends one macOS notification ("7 cached papers expire soon: review"). The notification opens `/cache/review/<batch_id>`, and the same batch goes to the agent inbox.

**5.8.4 Decisions.**

* Per item: Archive, Discard, Keep 30 more days, or Pin. Bulk buttons apply a choice to the whole batch.
* **Default when unanswered: keep, and ask again in 7 days. Unanswered items are never deleted.** The UI shows how many times each item has been asked about, so long-ignored items stand out.
* **From agent chat:** MCP tools `cache_review_list(batch_id)` and `cache_review_decide(batch_id, decisions[])`. Safeguards against prompt injection:
  * the call must name an existing open `batch_id` and only items in that batch
  * every decision is logged with the channel it came through
  * a discard through MCP is always the soft discard (7-day trash, undo in the UI)
  * the tool descriptions say decisions must come from the owner's explicit instruction
  * the tool annotations mark these tools as not read-only

**5.8.5 Archive target (Google Drive through the local sync folder, no new OAuth credential).**

* Path: `~/Library/CloudStorage/GoogleDrive-<account>/My Drive/Research Archive/<year>/`. The daemon detects the single `GoogleDrive-*` folder and the owner confirms it once in Settings. The account part is configurable.
* For each item it writes:
  * `<slug>.pdf` (or `<slug>.md` for doc pages)
  * a sidecar `<slug>.meta.json` with `title`, `authors`, `citation` (CSL-JSON plus a formatted APA string), `bibtex`, `source`, `source_id`, `doi`/`arxiv_id`, `original_url`, `fetched_at`, `archived_at`, `sha256`, `size_bytes`, and `archived_from` = "research-mcp v2"
* Write order: write to a `.partial` file in the target folder, fsync, rename, then read it back and check the size and SHA-256. Only after that check passes is the item removed from the cache (chunks, embeddings, PDF). The catalog row keeps the metadata, citation and archive path, so search can still answer "you archived this on <date>, at <path>".
* **Health check (an "Archive target" entry on the source board):**
  * the folder exists
  * the folder is writable (write and replace a fixed sentinel file, `.research-mcp-probe`)
  * Google Drive for desktop is running (process check)
  * free space on the volume

  Limitation: a successful local write only means Drive will upload the file, not that it already has. The UI says so.
* **Fallback:** if the Drive folder is missing or not writable, items go to `~/Research Archive/<year>/` (configurable) and are marked `archived_local_fallback`. A warning banner appears and a notification is sent ("Drive folder unavailable; 3 items archived locally"). A reconcile job moves those items into Drive once the health check passes again.

**5.8.6 Disk usage monitoring.** Every 15 minutes, record:

* total cache size, split into PDFs, `index.db` plus WAL, embeddings, model cache (fastembed) and trash
* free space on the cache volume and on the archive volume

Thresholds: warning when the cache passes 5 GB (configurable) or free disk drops below 15 GB; critical below 5 GB free. If the SQLite WAL grows past 256 MB, run a checkpoint. The UI shows growth per day.

**5.8.7 Backups (low priority by owner decision).**

* Every night, take a SQLite online backup (`.backup` API) of `state.db` only (config references, credential metadata, pins, archive catalog, review decisions, notification history) plus `config.toml`. Store them in `~/Library/Application Support/research-mcp/backups/` and keep 14 days. Optionally copy them into the Drive archive folder `Research Archive/_state/`.
* The cache index and embeddings are not backed up. They can be rebuilt, and the archive holds what matters.

### 5.9 Integrity and maintenance checks

| Check | Cadence | Action on failure |
|---|---|---|
| `PRAGMA quick_check` on index.db and state.db | daily | Mark the "Local cache" source `down`; offer a rebuild |
| FTS5 `INSERT INTO chunks_fts(chunks_fts) VALUES('integrity-check')` | daily | Offer an FTS `rebuild` |
| Missing files: catalog rows whose PDF is gone | daily | Mark the item `missing_file`; offer to re-fetch or drop it |
| Orphans: PDFs on disk with no row; embeddings with no chunk | daily | Report counts; offer cleanup (with confirmation) |
| Embedding coverage: chunks without embeddings | hourly | Queue an embed job automatically when the daemon is idle |
| Schema version (`PRAGMA user_version`) vs code | at start | Run migrations in a transaction; refuse to start on a downgrade |
| Dependency audit (pip-audit on the lockfile) | weekly | Notify on new advisories (PyMuPDF, duckdb, requests/httpx, mcp) |
| Upstream deprecation calendar | daily | Set `deprecated(days)` states |

Upgrade path:

* Pin dependencies with a uv lockfile.
* `research-mcp upgrade` stops the daemon, runs `uv sync`, runs migrations, runs doctor and restarts the daemon. If doctor fails, it rolls back to the previous venv.
* Keep `mcp<2` pinned until v2 is ported to the MCP SDK 2.x API.
* Preinstall the DuckDB extensions at install time so auto-install can stay off.

### 5.10 Local web UI

**Stack recommendation: Starlette with Jinja2 server-rendered pages and htmx (a vendored file, no CDN), running inside the daemon process.**

Why:

1. Starlette and uvicorn are already in the dependency tree through FastMCP's HTTP transports, so the UI only adds Jinja2 and one static JS file.
2. Server-side rendering reads the same core objects (registry, state.db, job service) directly. There's no second API to keep in sync and no JS build step.
3. htmx handles live refresh (polling every 10 s or SSE) and inline confirm dialogs with almost no JavaScript.
4. The UI is mostly read-only and single-user, so a single-page-app framework would add upkeep without benefit.

Rejected alternatives: Streamlit, Gradio and NiceGUI (they need a second process or impose their own app model, which conflicts with the daemon), and React/Vite (needs a build chain).

UI security:

* listens on 127.0.0.1 only, with the Host/Origin allowlist enforced
* the session starts from a one-time token URL opened by `research-mcp ui` (or a notification click) and is kept in an HttpOnly, SameSite=Strict cookie
* every POST carries a CSRF token
* every maintenance action needs an explicit confirmation that shows what will happen
* no page ever shows a secret value; only fingerprints and dates

**Pages, in navigation order:**

| # | Page | What it shows | Actions |
|---|---|---|---|
| 1 | **Source board** (home) | One tile or row per source (27 plus the local targets), grouped by category, with state chips: ok, degraded, down, unconfigured, credential expiring (days), credential invalid, quota low, deprecated (days). Each row: last probe, calls in 24 h, error rate, p95 latency, quota remaining and reset, last classified error, fix hint. Counts at the top ("24 ok, 1 degraded, 1 expiring, 1 deprecated"). | Run a probe now (one source or all); open the source detail (latency sparkline, errors by correlation id, recent calls); turn a source on or off. |
| 2 | **Credentials** | Per credential: name, which sources and tools use it, required or optional, storage (Keychain or env), fingerprint, Keychain modified date, `expires_at` with countdown, `rotate_by`, last validated, last result, status chip, and a link to that provider's steps for generating a new key. | Re-check now; reload from Keychain after rotating; set or clear `rotate_by`; acknowledge. Values are never entered in the browser (rotation happens in Keychain); the page offers a copyable `security add-generic-password -U -s research-mcp/<NAME> ...` command without the value. |
| 3 | **Quota and cost** | Per metered source: period allowance, used, remaining, reset date, rate of use, projected exhaustion date, budget cap and estimated spend (Brave, SerpAPI, OpenAlex). GitHub remaining per resource. | Edit budget caps and fan-out limits (with confirmation). |
| 4 | **Jobs** | Running, queued and recent jobs (index, embed, crawl, archive, reconcile, rebuild): kind, progress bar, start time, duration, message, cursor, error. | Cancel (with confirmation); retry failed jobs; view the log for a job id. |
| 5 | **Cache** (a simple cache view, not a library manager) | Table of cached items: title, source, size, fetched date, age, days to expiry, pinned, state. Totals: count, size by type, growth per day, free disk. A filter box and a search box (FTS over the cache, top 20 hits with snippets) answer "do I already have this?". | Pin or unpin; archive now; discard (to trash, with confirmation); open the original URL. |
| 6 | **Cache review** (`/cache/review/<batch_id>`) | The current expiring batch. Per item: title, citation, size, age, times already asked, and choices Archive, Discard, Keep 30 days or Pin. Bulk choices, and a reminder that unanswered items are kept and asked about again in 7 days. | Submit decisions; the confirmation shows a summary (N archived to <Drive path>, M discarded to trash for 7 days). |
| 7 | **Archive** | Archive target health (Drive folder found, writable, Drive app running, free space, fallback in use). Catalog of archived items with archived_at, path and a copy-citation button. Records of discarded items. Trash with undo until it is emptied. | Change the archive path (with confirmation); run reconcile; undo a discard within 7 days; copy the citation or BibTeX. |
| 8 | **Maintenance** | Last run and result of each check: integrity, orphan scan, embedding coverage, schema version, dependency audit, state backup. Disk usage panel. | Each needs confirmation: Verify now; Rebuild FTS; Re-embed missing; Clean orphans; Back up state now; Rebuild cache from archive (optional). |
| 9 | **Events and logs** | Notification history with acknowledged state. Recent WARN/ERROR log lines (redacted), searchable by correlation id, source or tool. | Acknowledge; snooze an alert for N days. |
| 10 | **Settings** (mostly read-only) | Effective config (paths, ports, thresholds, quiet hours, notification channels, archive target), which env vars are set (names only), versions (app, mcp, duckdb, pymupdf), launchd job status. | Edit thresholds, quiet hours and channels (with confirmation); send a test notification. |

### 5.11 MCP changes that support operations

* Add tool annotations to every tool (read-only or state-changing, open-world).
* Add the `ops_status` tool and the `research://status` resource (summary only).
* Add `cache_review_list` and `cache_review_decide`, with the safeguards in 5.8.4.
* Remove from MCP: caller-chosen paths, the hard delete in `remove_paper` (replace it with discard to trash), and raw SQL by default.
* Every tool response that carries fetched content uses the untrusted-content envelope.

## 6. Suggested fix order for v2

1. Close OPS-01, OPS-02, OPS-03, OPS-04, OPS-05 and OPS-08: harden DuckDB or remove raw SQL, scope credentials to their origin, send the Google key in a header, add redaction, and route every download through `download_pdf_atomic` into the confined cache.
2. Wire `Settings`, `security.py` and `jobs.py` in through an app factory (OPS-06). Build the daemon and stdio shim with HTTP bearer auth (OPS-07, OPS-12, OPS-13).
3. Keychain-backed secrets and credential metadata; then the source registry, passive telemetry and probes; then notifications (sections 3 and 5.2 to 5.5).
4. Handle the upstream changes: add `OPENALEX_API_KEY`, cap Brave fan-out and set budgets, and plan the Google PSE removal before 2027-01-01 (OPS-16).
5. Cache lifecycle with the 30-day review, Drive archive and disk monitoring (5.8). Integrity checks and embedding reconciliation (OPS-17, OPS-18).
6. UI pages in the order listed, with the Source board and Credentials first.
7. CI and dependency hygiene (OPS-22).

## 7. Sources

* GitHub changelog, PAT expiration options and the `GitHub-Authentication-Token-Expiration` header: https://github.blog/changelog/2021-07-26-expiration-options-for-personal-access-tokens/
* GitHub docs, token expiration and revocation (expiry, revocation after a public push, one year unused): https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/token-expiration-and-revocation
* GitHub docs, rate limit endpoint ("does not count against your REST API rate limit"; core, search, code_search): https://docs.github.com/zh/enterprise-server@3.21/rest/rate-limit/rate-limit
* Composer PR using the expiration header (an absent header means no expiry; example value format): https://github.com/composer/composer/pull/11688
* SerpApi Account API (free; fields `plan_searches_left`, `total_searches_left`, `plan_renewal_date`, `account_rate_limit_per_hour`): https://www.serpapi.com/account-api
* Brave Search API rate limiting headers (`X-RateLimit-Limit/Policy/Remaining/Reset`, 429 behavior): https://api-dashboard.search.brave.com/documentation/guides/rate-limiting
* Brave free tier removal and metered billing (secondary report): https://www.implicator.ai/brave-drops-free-search-api-tier-puts-all-developers-on-metered-billing.md
* Google Custom Search JSON API closed to new customers, shutdown 2027-01-01 (secondary summary): https://brave.com/learn/google-api-shutdown/
* Google Cloud, API key best practices (rotation, restrictions, avoid keys in query params, use `x-goog-api-key`): https://docs.cloud.google.com/docs/authentication/api%2Dkeys%2Dbest%2Dpractices
* Google Cloud, reauthentication (local ADC credentials expire with the Workspace session; `gcloud auth application-default login`): https://docs.cloud.google.com/docs/authentication/reauthentication
* Google Cloud, ADC troubleshooting: https://docs.cloud.google.com/docs/authentication/troubleshoot-adc
* Service account key expiry org policy `iam.serviceAccountKeyExpiryHours` (8 to 2160 h): https://www.infoq.com/news/2023/08/gcp-service-accounts-key-expiry
* Service account key validity (`validBeforeTime` for uploaded keys; created keys don't expire by default): https://jpassing.com/2021/07/17/limiting-the-validity-of-service-account-keys
* Google Developer Knowledge API quickstart (v1 and v1alpha, `searchDocumentChunks`, API key): https://developers.google.com/knowledge/quickstart
* OpenAlex deprecations (mailto polite pool ended February 2026, replaced by API keys): https://developers.openalex.org/guides/deprecations
* OpenAlex API key requirement and daily allowance (secondary report): https://casrai.org/news/openalex-api-keys-mandatory-usage-based-pricing-2026
* Semantic Scholar API overview (shared unauthenticated pool; keys recommended): https://semanticscholar.org/product/api
* DuckDB, securing DuckDB (`enable_external_access`, `allowed_directories`, autoload and autoinstall, `lock_configuration`, resource limits): https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview
* DuckDB VSS extension (data-loss warning for persisted HNSW indexes): https://duckdb.org/docs/current/core_extensions/vss
* MCP Python SDK 1.27 behavior (loopback default, DNS-rebinding protection, sync tools called inline): checked by reading the installed package source in the review environment.

Items marked "verify": CORE rate-limit headers and key expiry, OpenAlex usage headers, the Vertex AI Search rename and endpoint stability, and Brave's status codes for an invalid key. I couldn't reach primary docs for these.

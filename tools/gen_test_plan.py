"""Generates the acceptance catalog, traceability and Appendix A of TEST-PLAN-v3.md (TEST-PLAN-v1.md and TEST-PLAN-v2.md are frozen earlier versions; v2 is still cited by the running M0 plan and has the same M0 content).
Source of truth for test ids lives here; the hand-written parts of the plan live in
docs/test-plan/_plan_head.md and _plan_tail.md."""
import re, glob, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]

# (id, title, verifies, level, milestone, unit)
T = []
def t(i, title, fr, level, ms, unit=""):
    T.append((i, title, fr, level, ms, unit))

# ---------- M0 ----------
t("AT-PLAT-01","Package version is 3.x and matches pyproject metadata","FR-PLAT-58","unit","M0","M0-01")
t("AT-PLAT-02","tools/ci.sh exists, is executable and starts with #!/usr/bin/env bash","FR-PLAT-52","unit","M0","M0-01")
t("AT-PLAT-03","In a fresh subprocess, first import every third-party dependency and prime pydantic (define a throwaway model), then start recording with os.environ replaced by a recording mapping and an audit hook; importing research_mcp and every submodule, attributing only events whose frames are in research_mcp, reads no environment variable, opens no non-module file, creates no socket, starts no subprocess, makes no directory and adds no logging handler","FR-PLAT-04","unit","M0","M0-01")
t("AT-PLAT-05","tests/conftest.py blocks non-loopback sockets for every test not marked live, and live tests are deselected by default","NFR-09","unit","M0","M0-01")
t("AT-PLAT-04","pyproject declares extras pdf and embeddings; base dependencies exclude pymupdf, fastembed and duckdb","FR-PLAT-51","unit","M0","M0-01")
t("AT-SRCH-10","DOI normalization table: prefixes, resolver URLs, case, trailing punctuation, invalid forms rejected","FR-SRCH-10","unit","M0","M0-02")
t("AT-SRCH-11","arXiv normalization: 2410.18291v1 and 2410.18291 give the same id with the version separate; old-style ids; abs and pdf URLs","FR-SRCH-10, FR-SRCH-11","unit","M0","M0-02")
t("AT-SRCH-12","PMID, PMCID, OpenAlex, Semantic Scholar, CORE, NCT, RFC, handle and DSpace UUID canonical forms","FR-SRCH-10","unit","M0","M0-02")
t("AT-SRCH-13","URL normalization: scheme and host case, default ports, fragments and tracking parameters","FR-SRCH-10","unit","M0","M0-02")
t("AT-SRCH-14","parse_any detects schemes from prefixes, hosts and shapes (including github: and GitHub URLs); unknown input raises IdentifierError; file-name shapes such as doi_10.1145_3649835, core_123 and *.pdf are rejected","FR-SRCH-10, FR-SRCH-13","unit","M0","M0-02")
t("AT-SRCH-15","Property test: every normalizer is idempotent and stable under case and whitespace changes","FR-SRCH-10","unit","M0","M0-02")
t("AT-SRCH-16","title_key: Unicode normalization, casefold, punctuation and stop words","FR-SRCH-12","unit","M0","M0-02")
t("AT-PLAT-30","ToolResult serializes to the envelope shape and exposes a JSON schema","FR-PLAT-30","unit","M0","M0-03")
t("AT-PLAT-31","Budget trims items and long text to the byte limit, sets truncated and keeps the cursor","FR-PLAT-30, NFR-05","unit","M0","M0-03")
t("AT-PLAT-32","ErrorCode contains every code in PRD-platform FR-PLAT-32 and ToolError carries code, message, retryable, correlation_id","FR-PLAT-32","unit","M0","M0-03")
t("AT-PLAT-33","Untrusted envelope marks fetched text with untrusted=true and its source","FR-PLAT-25, NFR-06","unit","M0","M0-03")
t("AT-PLAT-06","core.specs and core.models types validate (SourcePolicy, AuthSpec origins, SearchFilters bounds, Work, CallRecord); research_mcp.testing.clock.FakeClock advances time deterministically","FR-SRC-01, FR-PLAT-30","unit","M0","M0-03")
t("AT-PLAT-34","Cursors are HMAC signed with a key passed in; a tampered or foreign cursor is rejected with invalid_argument","FR-SRCH-06","unit","M0","M0-03")
t("AT-PLAT-08","Settings load from config.toml with RESEARCH_MCP_ environment overrides; invalid values fail with a clear message; defaults match LLD section 2 (including cache.retention_days = 120)","FR-PLAT-08, FR-CACHE-30","unit","M0","M0-04")
t("AT-PLAT-09","Default paths: state and cache data under ~/Library/Application Support/research-mcp (never ~/Library/Caches), models under ~/Library/Caches, logs under ~/Library/Logs; directories created with mode 0700","FR-PLAT-09, FR-CACHE-59","unit","M0","M0-04")
t("AT-PLAT-10","A non-loopback server.host is rejected","FR-PLAT-03, NFR-07","unit","M0","M0-04")
t("AT-PLAT-11","contact.email placeholder values (example.com, example.org, .test, .invalid) are rejected by settings validation; an unset email is allowed","FR-SRC-11, NFR-08","unit","M0","M0-04")
t("AT-PLAT-12","Secret references (keychain:research-mcp/NAME, env:NAME) parse; malformed references fail","FR-PLAT-10","unit","M0","M0-05")
t("AT-SEC-01","Secret repr, str, format and logging never contain the value; fingerprint is sha256[:8]","FR-PLAT-11, NFR-04","unit","M0","M0-05")
t("AT-SEC-02","KeychainProvider (with an injected runner) calls /usr/bin/security with the expected argv and a 5 s timeout; exit 44 maps to missing, a locked keychain to keychain_locked; stderr is never echoed","FR-PLAT-10, NFR-03","unit","M0","M0-05")
t("AT-SEC-13","SecretProvider.set writes through security -i on stdin; the value never appears in any recorded argv","FR-PLAT-10, FR-PLAT-16","unit","M0","M0-05")
t("AT-SEC-03","Keychain metadata lookup never passes -w and returns the modification date only","FR-HLTH-20","unit","M0","M0-05")
t("AT-SEC-04","SecretCache.reload re-reads secrets and returns the names whose fingerprints changed","FR-PLAT-15, FR-HLTH-23","unit","M0","M0-05")
t("AT-SEC-05","Known secret values are masked in log messages, args and exception text, including records from child and third-party loggers (filter on handlers)","FR-PLAT-13, NFR-04","unit","M0","M0-06")
t("AT-SEC-06","Credential patterns (key=, api_key=, token=, Authorization, X-Subscription-Token, x-goog-api-key, AIza, ghp_, github_pat_) are masked","FR-PLAT-13","unit","M0","M0-06")
t("AT-SEC-14","configure_logging sets httpx, httpcore, uvicorn.access and mcp loggers to WARNING; an INFO httpx record with api_key in the URL never reaches a handler unmasked","FR-PLAT-13","unit","M0","M0-06")
t("AT-SEC-07","Property test: random secrets registered with the redactor never appear in any formatted log record","FR-PLAT-13, NFR-04","unit","M0","M0-06")
t("AT-PLAT-40","Logging writes JSON lines to the rotating file (10 MB x 5) and only warnings and errors to stderr","FR-PLAT-40","unit","M0","M0-06")
t("AT-PLAT-41","Log records carry correlation_id and the fields in FR-PLAT-41","FR-PLAT-41","unit","M0","M0-06")
t("AT-PLAT-42","Query text is logged as hash and length unless debug is on","FR-PLAT-42","unit","M0","M0-06")
t("AT-PLAT-35","429 with Retry-After is retried after the stated delay through the injected sleeper; delays over 60 s fail at once as rate_limited with retry_after_ms; three 429s end as rate_limited with the last retry_after_ms","FR-PLAT-33","unit","M0","M0-07")
t("AT-PLAT-36","500, 502, 503, 504 and connection errors retry up to 3 attempts with jittered backoff, then upstream_error; other 4xx do not retry; a host outside the policy fails with blocked_by_policy","FR-PLAT-33","unit","M0","M0-07")
t("AT-PLAT-37","Per-source token bucket is shared by all callers: two concurrent arXiv calls are spaced 3 s apart (fake clock)","FR-PLAT-33, NFR-08","unit","M0","M0-07")
t("AT-PLAT-38","Streaming byte cap aborts with too_large before the whole body is read","FR-PLAT-33","unit","M0","M0-07")
t("AT-PLAT-39","Every request sends the user agent with the owner contact; every attempt emits a call record","FR-PLAT-33, FR-HLTH-01, NFR-08","unit","M0","M0-07")
t("AT-SEC-08","A credential is attached only when the request origin is in its spec origins (the CORE key is not sent to a third-party PDF host)","FR-PLAT-12, FR-CACHE-03","unit","M0","M0-07")
t("AT-SEC-09","Header placement is used when the spec allows it (x-goog-api-key); with query placement the URL never appears in logs or errors","FR-PLAT-12, FR-PLAT-14","unit","M0","M0-07")
t("AT-SEC-10","HttpError messages contain no exception text, URL query or upstream body","FR-PLAT-14, NFR-04","unit","M0","M0-07")
t("AT-CACHE-01","Downloader (with an injected resolver) rejects http, private, loopback and link-local IPs, also after a redirect; pins the connection to the checked IP so a second resolution to a private IP (DNS rebinding) is never used; rejects wrong media types, wrong magic bytes and oversize bodies","FR-CACHE-02","unit","M0","M0-07")
t("AT-CACHE-02","Downloader writes atomically under data_dir/files by SHA-256 and returns full provenance","FR-CACHE-02, FR-CACHE-04, FR-CACHE-05","unit","M0","M0-07")
t("AT-PLAT-50","Migrations run inside explicit BEGIN IMMEDIATE and COMMIT (a failing script leaves no partial schema) and set user_version for state.db and cache.db; SQLite older than 3.37 is refused","FR-PLAT-56","unit","M0","M0-08")
t("AT-PLAT-51","Opening a database newer than the code fails with a clear error","FR-PLAT-56","unit","M0","M0-08")
t("AT-PLAT-52","Connections use WAL, foreign_keys=ON and busy_timeout; writes are serialized","FR-PLAT-05","unit","M0","M0-08")
t("AT-PLAT-53","Schemas match LLD 8.1 and 10.1; the external-content FTS table stays in sync through triggers and snippet() returns text; CHECK constraints hold for archived and discarded documents; collections do not pin by default","FR-CACHE-30, FR-CACHE-36, FR-CACHE-55","unit","M0","M0-08")
t("AT-SRC-01","SourceSpec validation: required fields, rate and timeout bounds, auth origins non-empty when auth is set","FR-SRC-01","unit","M0","M0-09")
t("AT-SRC-02","Registry discovers built-ins and builds two instances of one adapter from configuration alone","FR-SRC-04","unit","M0","M0-09")
t("AT-SRC-03","A disabled source is never called and reports state disabled","FR-SRC-05","unit","M0","M0-09")
t("AT-SRC-04","A source missing a required credential, or a source with needs_contact while contact.email is unset, reports unconfigured with the exact fix","FR-SRC-06, FR-SRC-11","unit","M0","M0-09")
t("AT-SRC-05","A source missing an optional extra reports unconfigured with the install command","FR-SRC-07","unit","M0","M0-09")
t("AT-SRC-06","Conformance suite runs the eight checks of LLD 5.2 (with an injected sleeper and FakeClock) against every registered adapter; in this unit the fake adapter from research_mcp.testing.adapters","FR-SRC-02, FR-SRC-08, FR-SRC-09","unit","M0","M0-09")
t("AT-SRC-07","Static check: no module under sources/ imports httpx, requests, urllib.request, http.client, socket, research_mcp.platform.secrets, or calls time.sleep or asyncio.sleep (urllib.parse is allowed)","FR-SRC-03","unit","M0","M0-09")
t("AT-SRC-10","arXiv adapter passes conformance (run with -k); uses https; maps versions; spec rate is 1 request per 3 s with concurrency 1","FR-SRC-08, FR-SRC-09, NFR-08","integration","M0","M0-10")
t("AT-SRC-11","Crossref adapter passes conformance (run with -k); sends mailto; maps DOIs and issued dates; declares updates capability","FR-SRC-08, FR-SRC-09, FR-SRC-11","integration","M0","M0-11")
t("AT-SRC-12","OpenAlex adapter passes conformance (run with -k); sends the API key per spec; page size at most 100; uses topics and last_known_institutions; its error classifier maps an insufficient-budget 429 to budget_exhausted with detail","FR-SRC-08, FR-SRC-09","integration","M0","M0-12")
t("AT-SRCH-01","Fan-out runs sources concurrently: three fake sources of 1 s each finish in about 1 s","FR-SRCH-03, NFR-02","integration","M0","M0-13")
t("AT-SRCH-02","A slow source is cancelled at its timeout or the deadline and reported as timeout; others return","FR-SRCH-03, FR-SRCH-04","integration","M0","M0-13")
t("AT-SRCH-03","A failing source never fails the search; every selected source has a status entry","FR-SRCH-04","integration","M0","M0-13")
t("AT-SRCH-04","Records sharing any identifier merge into one work with found_in listing every source","FR-SRCH-05, FR-SRCH-11","integration","M0","M0-13")
t("AT-SRCH-05","Title, year and first-author matches merge and are flagged fuzzy","FR-SRCH-12","integration","M0","M0-13")
t("AT-SRCH-06","Ranking is reciprocal rank fusion with the multi-source boost (golden ordering)","FR-SRCH-05","integration","M0","M0-13")
t("AT-SRCH-07","The combined cursor continues each source from its own cursor; exhausted sources report empty","FR-SRCH-06","integration","M0","M0-13")
t("AT-SRCH-08","auto selects enabled sources from the default groups and skips unconfigured, disabled and down sources with their status","FR-SRCH-02, FR-SRCH-08, FR-HLTH-12","integration","M0","M0-13")
t("AT-SRCH-09","Disagreeing fields across sources are recorded with their sources","FR-SRCH-14","integration","M0","M0-13")
t("AT-SRCH-17","get_work merges records from every source that understands the identifier and lists OA locations","FR-SRCH-15, FR-SRCH-16","integration","M0","M0-13")
t("AT-SRCH-20","search tool through an in-memory MCP client returns structured content matching its output schema","FR-SRCH-01, FR-PLAT-30","contract","M0","M0-14")
t("AT-SRCH-21","Out-of-range and unknown arguments are rejected before any source is called","FR-PLAT-31","contract","M0","M0-14")
t("AT-SRCH-22","compact detail trims authors and abstracts; full detail fits the budget","FR-SRCH-07","contract","M0","M0-14")
t("AT-SRCH-23","get_work tool accepts prefixed ids, bare DOIs, resolver URLs and arXiv URLs","FR-SRCH-15","contract","M0","M0-14")
t("AT-SRC-08","list_sources tool and research://sources resource list every source with state and fix hint","FR-SRC-05, FR-SRC-06, FR-HLTH-42","contract","M0","M0-14")
t("AT-PLAT-60","Every registered tool declares readOnlyHint, destructiveHint, idempotentHint and openWorldHint","FR-PLAT-26","contract","M0","M0-14")
t("AT-PLAT-61","Server instructions state the untrusted-content rule and the owner-decision rule for reviews","FR-PLAT-25, FR-CACHE-35","contract","M0","M0-14")
t("AT-PLAT-62","A tool that hits an internal error returns code, message, retryable and correlation_id with no exception text","FR-PLAT-14, FR-PLAT-32","contract","M0","M0-14")
t("AT-PLAT-63","Tool results never exceed limits.response_bytes","FR-PLAT-30, NFR-05","contract","M0","M0-14")
t("AT-PLAT-70","build_app opens and closes every component in its lifespan; /healthz and /readyz answer","FR-PLAT-04, FR-HLTH-43","integration","M0","M0-15")
t("AT-SEC-11","MCP and /api requests without the bearer token get 401; the comparison uses hmac.compare_digest","FR-PLAT-03, NFR-07","integration","M0","M0-15")
t("AT-SEC-12","Requests with a foreign Host or Origin are refused","FR-PLAT-03","integration","M0","M0-15")
t("AT-PLAT-71","The daemon refuses to bind a non-loopback address","FR-PLAT-03, NFR-07","integration","M0","M0-15")
t("AT-PLAT-72","The stdio shim relays a full MCP session to an in-process daemon (initialize, list tools, call search)","FR-PLAT-02, NFR-01","integration","M0","M0-15")
t("AT-PLAT-73","With the daemon down the shim asks launchd to start it (fake launchctl), retries, then returns one clear MCP error","FR-PLAT-02","integration","M0","M0-15")
t("AT-PLAT-74","Jobs: submit, status, progress and cancel persist in state.db","FR-PLAT-06","integration","M0","M0-15")
t("AT-PLAT-75","The event loop stays responsive (heartbeat gap under 200 ms) while a slow fake source runs","FR-PLAT-05, NFR-02","integration","M0","M0-15")
t("AT-PLAT-76","Scheduler compares wall-clock due times every 60 s and runs a missed daily job exactly once after a simulated sleep or restart (FakeClock)","FR-PLAT-06","integration","M0","M0-15")
t("AT-PLAT-77","MCP is mounted stateless at /mcp: the shim keeps working across a daemon restart and replays initialize once on a session error","FR-PLAT-02, NFR-01","integration","M0","M0-15")
t("AT-PLAT-80","research-mcp --help lists serve, stdio, doctor, ui, sources, config, install, upgrade, secrets, import-legacy","FR-PLAT-50","unit","M0","M0-16")
t("AT-PLAT-81","install renders the daemon, watchdog and doctor launchd plists with every placeholder filled; plistlib parses them; nothing secret is written","FR-PLAT-54, FR-HLTH-41","unit","M0","M0-16")
t("AT-PLAT-82","install --print-client-config prints entries that launch research-mcp stdio and contain no secret","FR-PLAT-54, FR-MIG-20","unit","M0","M0-16")
t("AT-PLAT-83","install generates DAEMON_TOKEN through the secret provider if absent; secrets rotate-token replaces it and the old token stops working","FR-PLAT-16","unit","M0","M0-16")
t("AT-SRC-13","gen_inventory --check fails when the committed source inventory differs from the registry","FR-SRC-13, NFR-10","unit","M0","M0-16")
t("AT-HLTH-40","doctor (skeleton) runs daemon_alive, keychain_readable, contact_email and schema_versions with fakes; --liveness runs only the first two; --json output; exit code reflects criticals","FR-HLTH-40","unit","M0","M0-16")

# ---------- M1 ----------
t("AT-SRC-20","Every M1 adapter in PRD-sources section 3 passes the conformance suite with its own fixtures","FR-SRC-08, FR-SRC-09, FR-SRC-16","integration","M1")
t("AT-SRC-21","Four DSpace instances come from configuration with one adapter module; each records its DSpace version","FR-SRC-04","integration","M1")
t("AT-SRC-22","Upstream MCP adapters (AWS Knowledge, Microsoft Learn) go through McpUpstreamPort, so rate limits, host policy, telemetry and redaction apply (MCP server fake)","FR-SRC-10","integration","M1")
t("AT-SRC-23","Docs-site adapter refuses hosts and paths outside its allowlist (including substring tricks) and honors robots.txt","FR-SRC-15","integration","M1")
t("AT-SRC-24","A source with a shutdown date reports deprecated(days)","FR-SRC-14","unit","M1")
t("AT-SRC-25","sources check --live writes refreshed fixtures to a review folder only (opt-in live test)","FR-SRC-12","live","M1")
t("AT-SRC-26","Every upstream endpoint v1 calls maps to a registered v2 source (table-driven from the MIGRATION tool map, with the AWS and Microsoft Learn substitution listed); defaults.toml holds site set v1_docs with v1's 26 domains and the six docs_site instances with v1's seeds and filters","FR-SRC-17, FR-SRC-18","unit","M1")
t("AT-SRC-27","Site sets load from config and defaults; config overrides defaults; an invalid set name fails validation","FR-SRC-18","unit","M1")
t("AT-SRC-28","Web sources are disabled until their settings and credential are present; auto selection never includes the web group; naming the group or a source id selects them","FR-SRC-19","integration","M1")
t("AT-SRC-29","Daily cap: at budget_cap calls a web source reports budget_exhausted until the next local midnight (FakeClock) and federation skips it with that status","FR-SRC-20, FR-HLTH-12","integration","M1")
t("AT-SRC-30","Fallback strategy: with Vertex exhausted and Brave failing, SerpAPI answers, Programmable Search reports not_needed, and only one paid query per page is spent; strategy all fans out to every configured web source; non-web sources still run in parallel within the deadline","FR-SRC-21","integration","M1")
t("AT-SRC-31","site_set: Brave queries are split into at most 3 batches of at most 380 characters with query-named domains first; SerpAPI and Programmable Search use one query and set truncated when domains are dropped; Vertex results are filtered by host; an unknown set is invalid_argument before any call","FR-SRC-22","unit","M1")
t("AT-SRC-32","Vertex adapter passes conformance; GoogleAdcProvider (fake loader) refreshes off the event loop; the token goes only to discoveryengine.googleapis.com with X-Goog-User-Project; static check that v2 code never opens the credential file; the refresh call is recorded as a call record","FR-SRC-23, FR-PLAT-10","integration","M1")
t("AT-SRC-33","Brave, SerpAPI and Programmable Search adapters pass conformance; Brave sends X-Subscription-Token, Programmable Search sends x-goog-api-key and reports deprecated(days); the SerpAPI api_key never appears in logs, errors, call records or tool results","FR-SRC-19, FR-PLAT-12, FR-PLAT-13","integration","M1")
t("AT-PLAT-13","pyproject declares the gcp extra (google-auth); base dependencies exclude google-auth; without the extra, vertex_search reports unconfigured with the install command","FR-PLAT-51, FR-SRC-07","unit","M1")
t("AT-SRCH-30","citations merges OpenCitations, OpenAlex and Semantic Scholar, dedupes by DOI, fills titles and pages","FR-SRCH-20","integration","M1")
t("AT-SRCH-31","authors merges OpenAlex, ORCID and DBLP records","FR-SRCH-21","integration","M1")
t("AT-SRCH-32","cite exports BibTeX, CSL-JSON, RIS and text; non-DOI works format from the CSL snapshot; unknown style or format is rejected","FR-SRCH-22","integration","M1")
t("AT-SRCH-33","check_integrity reports retractions and corrections including Retraction Watch records (golden fixtures)","FR-SRCH-25","integration","M1")
t("AT-SRCH-34","search records query hash, sources, statuses and timings; text only in debug","FR-SRCH-09","integration","M1")
t("AT-HLTH-01","Call telemetry rows and hourly rollups are written and pruned on schedule","FR-HLTH-01","integration","M1")
t("AT-HLTH-02","Probes run at their cadence with jitter through the rate limiter; a recent successful call skips the probe","FR-HLTH-02, FR-HLTH-04","integration","M1")
t("AT-HLTH-03","A 200 response with a changed shape marks the source down","FR-HLTH-03","integration","M1")
t("AT-HLTH-04","Local targets (cache db, archive folder, disk) have probes","FR-HLTH-05","integration","M1")
t("AT-HLTH-10","State evaluation table: each rule in PRD-health 2.2 produces its state, worst state wins","FR-HLTH-10","unit","M1")
t("AT-HLTH-12","rate_limited(until) and budget_exhausted(reset) states are set from 429 and budget responses and cleared at their times","FR-HLTH-10, FR-HLTH-12","unit","M1")
t("AT-HLTH-13","A locked Keychain gives every credential keychain_locked and produces exactly one notification","FR-HLTH-20, FR-HLTH-30","unit","M1")
t("AT-HLTH-11","Source detail exposes every field in FR-HLTH-11","FR-HLTH-11","integration","M1")
t("AT-HLTH-20","Credential states: ok, expiring_soon, invalid, missing, quota_low, unknown_expiry from fixtures","FR-HLTH-20, FR-HLTH-21","unit","M1")
t("AT-HLTH-21","GitHub expiry header and /rate_limit update expires_at and quota","FR-HLTH-21","integration","M1")
t("AT-HLTH-22","Keys without expiry get rotate_by 180 days after Keychain modification unless overridden","FR-HLTH-22","unit","M1")
t("AT-HLTH-23","Fix text names the Keychain item, the provider page and a security command with no value","FR-HLTH-24","unit","M1")
t("AT-HLTH-24","Google sign-in states from fakes: no sign-in is missing; refused refresh, SERVICE_DISABLED and PERMISSION_DENIED are invalid with their reason; fix text gives gcloud auth application-default login; metadata holds account email and token expiry only; token renewal never raises expiring_soon","FR-HLTH-25","unit","M1")
t("AT-HLTH-25","Metered sources validate with free methods where they exist (SerpAPI account endpoint, Vertex engine metadata); Brave and Programmable Search probes run at most once per 24 h; Brave rate-limit headers update quota","FR-HLTH-21","integration","M1")
t("AT-HLTH-30","Notifications fire on state changes and expiry milestones (14, 7, 3, 1 days) only once each","FR-HLTH-30","integration","M1")
t("AT-HLTH-31","Unresolved items roll into one daily digest","FR-HLTH-31","integration","M1")
t("AT-HLTH-32","macOS notifier argv uses terminal-notifier -execute research-mcp ui --path (no token anywhere in argv), osascript fallback; webhook payload carries the Keychain token in a header, never in the URL","FR-HLTH-32, FR-UI-02, NFR-03","unit","M1")
t("AT-HLTH-33","Quiet hours hold non-critical notifications; a recently used invalid credential notifies immediately","FR-HLTH-33","unit","M1")
t("AT-HLTH-34","Notification subjects and bodies never contain secret values or URLs with queries","FR-HLTH-34, NFR-04","unit","M1")
t("AT-HLTH-35","Notifications store acknowledged and snoozed state","FR-HLTH-35","unit","M1")
t("AT-HLTH-41","doctor runs every check in LLD 10.5 with fakes (including archive_access with a simulated TCC denial, review_overdue and backup_recent); --notify sends one summary only when the result changes","FR-HLTH-40, FR-HLTH-41, FR-CACHE-45","integration","M2")
t("AT-HLTH-42","ops_status, research://status and /api/status expose status without secrets","FR-HLTH-42, FR-HLTH-43","contract","M1")

# ---------- M2 ----------
t("AT-CACHE-10","fetch picks the best OA location by preference across sources and returns a doc handle with summary","FR-CACHE-01","integration","M2")
t("AT-CACHE-11","No tool accepts a local path; fetch writes only under the cache root","FR-CACHE-04, FR-PLAT-21","contract","M2")
t("AT-CACHE-12","Fetch of a cached work returns it; fetch of a discarded work re-fetches from its recipe","FR-CACHE-06","integration","M2")
t("AT-CACHE-13","Multi-document fetch and crawl run as jobs with progress and cancel","FR-CACHE-07, FR-CACHE-56","integration","M2")
t("AT-CACHE-14","A parser crash or timeout in a worker marks extract_failed and the daemon keeps serving","FR-CACHE-10","integration","M2")
t("AT-CACHE-15","Chunker golden tests: target size, overlap, paragraph and sentence boundaries, no split words, offsets and pages","FR-CACHE-11","unit","M2")
t("AT-CACHE-16","HTML keeps h1 to h3 sections; a 36 KB single-line page yields bounded chunks under the hard cap","FR-CACHE-12","unit","M2")
t("AT-CACHE-17","Image-only PDFs are flagged needs_ocr","FR-CACHE-13","unit","M2")
t("AT-CACHE-18","Extractions record parser, parser version and chunker version","FR-CACHE-14","unit","M2")
t("AT-CACHE-19","read returns bounded windows by page, section and chunk with a cursor","FR-CACHE-15","contract","M2")
t("AT-CACHE-20","search_cache keyword, semantic and hybrid modes; invalid FTS syntax falls back to literal; coverage reported","FR-CACHE-16, FR-CACHE-17","integration","M2")
t("AT-CACHE-21","library list and stats report states, sizes, ages and expiry","FR-CACHE-18","contract","M2")
t("AT-CACHE-22","Every chunk is embedded at fetch; vectors keyed by content hash and model; removed with chunks","FR-CACHE-20, FR-CACHE-21, FR-CACHE-23","integration","M2")
t("AT-CACHE-23","Queries use query encoding and passages passage encoding (fake model records calls)","FR-CACHE-22","unit","M2")
t("AT-CACHE-24","Without the embeddings extra, search_cache runs keyword-only and says so","FR-CACHE-24","integration","M2")
t("AT-CACHE-30","Lifecycle transition table of LLD 9.1, one test per row, with a fake clock","FR-CACHE-30, FR-CACHE-31, FR-CACHE-34, FR-CACHE-36, FR-CACHE-37","unit","M2")
t("AT-CACHE-31","Daily review builds one batch, sends one notification and one webhook message","FR-CACHE-31, FR-CACHE-32","integration","M2")
t("AT-CACHE-32","Per-item and bulk decisions apply archive, discard, keep and pin","FR-CACHE-33","integration","M2")
t("AT-CACHE-33","Unanswered items are never deleted: 90 simulated days with no answers delete nothing","FR-CACHE-34","integration","M2")
t("AT-CACHE-34","cache_review_decide rejects closed batches and items outside the batch, records decided_by=agent and channel=mcp, sends discards to trash only, and immediately notifies the owner of MCP discards with an undo link","FR-CACHE-35, FR-PLAT-27","contract","M2")
t("AT-CACHE-35","Review items show citation, size, age, times asked, last access and integrity changes","FR-CACHE-38, FR-SRCH-26","integration","M2")
t("AT-CACHE-36","Discard keeps work metadata, CSL and recipe; undo within 7 days restores files; owner notified 24 hours before purge; after 7 days files are removed; a file shared by SHA-256 with another live document is never removed","FR-CACHE-36, FR-SRCH-23","integration","M2")
t("AT-CACHE-40","Archive target auto-detects the GoogleDrive folder and writes file plus sidecar with the fields in LLD 9.3","FR-CACHE-45, FR-CACHE-46","integration","M2")
t("AT-CACHE-41","Archive verifies by reading back size and SHA-256 before removing the cached copy; a failed verify keeps the cache copy","FR-CACHE-47","integration","M2")
t("AT-CACHE-42","Unavailable target uses the fallback, warns, and reconcile moves items later","FR-CACHE-48","integration","M2")
t("AT-CACHE-43","Archived items keep their extraction, chunks, FTS rows and embeddings: search_cache and read return them after archiving; library and get_work report the Drive path and date; cite works","FR-CACHE-49","integration","M2")
t("AT-CACHE-44","Archive target health covers exists, writable, privacy access, Drive app running and free space; upload state moves pending to uploaded through a fake file-provider check, and a 24-hour stall notifies","FR-CACHE-50","integration","M2")
t("AT-CACHE-45","Collections create, add, remove, list, show; collections do not pin unless created with pin_members; pinning collections pin and unpin members","FR-CACHE-55","integration","M2")
t("AT-CACHE-46","Disk samples, thresholds and notifications","FR-CACHE-57","integration","M2")
t("AT-CACHE-47","Integrity checks detect corrupt FTS, missing files and orphans; fixes run only as confirmed jobs","FR-CACHE-58","integration","M2")
t("AT-CACHE-60","archive reindex rebuilds works, identifiers and archived documents from a temp Drive folder of PDFs and sidecars, re-extracts missing text, verifies sha256, reports files without sidecars, and leaves the Drive files byte-for-byte unchanged","FR-CACHE-51","integration","M2")
t("AT-CACHE-61","search_cache marks each hit cached, pinned or archived and filters by states; an archived hit points to its Drive path","FR-CACHE-52","contract","M2")
t("AT-CACHE-48","library offers no discard action; only cache_review_decide and the UI can discard","FR-CACHE-35","contract","M2")
t("AT-CACHE-49","Nightly backup copies state.db, cache.db and config.toml with the online backup API and keeps 7","FR-PLAT-57, FR-CACHE-59","integration","M2")
t("AT-SEC-20","No MCP tool performs a hard delete","FR-PLAT-27","contract","M2")
t("AT-SEC-21","No SQL tool is registered; any internal DuckDB connection has external access off and configuration locked","FR-PLAT-20, FR-PLAT-22","contract","M2")
t("AT-SEC-22","Fetched text in read, search_cache and get_work is always inside the untrusted envelope","FR-PLAT-25, NFR-06","contract","M2")
t("AT-SEC-23","Hostile PDF corpus (malformed, huge page count, decompression bombs) never crashes the daemon","FR-CACHE-10","integration","M2")

t("AT-SRCH-36","get_work reports integrity status and cache state (cached, pinned, archived, discarded, none)","FR-SRCH-17","integration","M2")

# ---------- M3 ----------
t("AT-UI-01","UI is served only on loopback under /ui with no external assets","FR-UI-01, FR-UI-06","integration","M3")
t("AT-UI-02","research-mcp ui mints a one-time token at use time; login sets an HttpOnly SameSite=Strict cookie with Path=/; tokens expire, cannot be reused, and never appear in access logs (uvicorn access log off)","FR-UI-02","integration","M3")
t("AT-UI-03","POSTs without a valid CSRF token are refused; maintenance actions require confirmation","FR-UI-03","integration","M3")
t("AT-UI-04","Rendered pages never contain a registered secret value (scan every page with fake secrets)","FR-UI-04, NFR-04","integration","M3")
t("AT-UI-05","Fragments refresh through htmx endpoints","FR-UI-05","integration","M3")
t("AT-UI-06","UI strings contain no em dashes or en dashes","FR-UI-07, NFR-11","unit","M3")
t("AT-UI-10","Source board shows counts, groups, state chips and per-row fields; probe and enable actions work","FR-UI-10","integration","M3")
t("AT-UI-11","Credentials page shows metadata only and the value-free security command","FR-UI-11","integration","M3")
t("AT-UI-12","Quota page shows allowance, used, remaining, reset and projection","FR-UI-12","integration","M3")
t("AT-UI-13","Jobs page lists jobs and cancels with confirmation","FR-UI-13","integration","M3")
t("AT-UI-14","Cache page lists items with totals and the do-I-have-this search","FR-UI-14","integration","M3")
t("AT-UI-15","Review page submits per-item and bulk decisions with a summary confirmation","FR-UI-15","integration","M3")
t("AT-UI-16","Archive page shows target health, catalog, discards and trash undo","FR-UI-16","integration","M3")
t("AT-UI-17","Maintenance page runs confirmed actions","FR-UI-17","integration","M3")
t("AT-UI-18","Events page lists notifications and redacted logs searchable by correlation id","FR-UI-18","integration","M3")
t("AT-UI-19","Settings page shows effective config and names only for credentials; test notification works","FR-UI-19","integration","M3")

# ---------- M4 ----------
t("AT-MIG-01","secrets import reads fake client configs, writes Keychain items through a fake provider, prints names and fingerprints only","FR-MIG-01","integration","M4")
t("AT-MIG-02","Conflicting values for one name stop the import for that name and ask","FR-MIG-02","integration","M4")
t("AT-MIG-03","The Brave, SerpAPI and shared Google keys are imported; a v1 credential no v2 source uses is reported as not imported and not copied","FR-MIG-03","unit","M4")
t("AT-MIG-04","secrets import is idempotent and --dry-run writes nothing","FR-MIG-04","integration","M4")
t("AT-MIG-05","scrub-client-configs backs up each file and removes only v1 env values after confirmation","FR-MIG-05","integration","M4")
t("AT-MIG-06","v1 web-search settings become config: VERTEX_AI_* gives instance vertex_v1, GOOGLE_PSE_CX gives sources.google_pse.engine_id, a named v1 provider goes first in web.order; every written setting is printed","FR-MIG-06","unit","M4")
t("AT-MIG-10","import-legacy opens the v1 database immutable and leaves the v1 folder byte-for-byte unchanged","FR-MIG-10, FR-MIG-15","integration","M4")
t("AT-MIG-11","On a synthetic v1 database with the 54-pair pattern, 10 URL rows and harv and penn ids, the import produces the expected works, HTML documents and legacy ids","FR-MIG-11","integration","M4")
t("AT-MIG-12","Re-extraction is used; v1 chunks are imported only where it fails","FR-MIG-12","integration","M4")
t("AT-MIG-13","Mode cache gives every item a fresh 120-day expiry","FR-MIG-13","integration","M4")
t("AT-MIG-14","The report contains every field in FR-MIG-14","FR-MIG-14","integration","M4")
t("AT-MIG-20","Client config printer output for Claude desktop, Claude Code and OpenClaw","FR-MIG-20, FR-MIG-21","unit","M4")
t("AT-MIG-21","The tool map covers all 53 v1 tools","FR-MIG-22","unit","M4")

# ---------- cross-cutting process items, not unit tests ----------
OWNER = [
("OC-01","On the Mac: install, doctor green, a client searches three sources through the shim","FR-PLAT-01, FR-PLAT-54","M0"),
("OC-02","On the Mac: the daemon reads every Keychain item with no prompt; doctor shows each credential state","FR-PLAT-10","M0"),
("OC-13","On the Mac: install triggers the Google Drive privacy prompt in the foreground; doctor archive_access passes afterward","FR-CACHE-45","M2"),
("OC-03","On the Mac: a real macOS notification for a forced credential state opens the right UI page","FR-HLTH-32","M1"),
("OC-04","On the Mac: one real archive written to the Drive folder, visible in Drive on the web","FR-CACHE-45, FR-CACHE-47","M2"),
("OC-05","Owner walkthrough of every UI page","FR-UI-10, FR-UI-19","M3"),
("OC-06","Cutover steps 1 to 9 of MIGRATION-v2 completed","FR-MIG-20, FR-MIG-21, FR-MIG-23","M4"),
("OC-07","14 days on v2 with no fallback; owner approves retiring v1","FR-MIG-24","M4"),
("OC-08","CI on GitHub Actions (macOS and Linux, 3.12 and 3.13) with secret scan and weekly audit, once a remote exists","FR-PLAT-53","M1"),
("OC-09","Upgrade with a forced doctor failure rolls back","FR-PLAT-55","M3"),
("OC-10","Nightly state backup present for 3 days; optional Drive copy","FR-PLAT-57","M2"),
("OC-11","A new free source added by an agent in one work unit, touching only the allowed files","FR-SRC-16, G3","M1"),
("OC-12","Five-source live search p95 under 8 s over 20 runs","G2, FR-SRCH-03","M1"),
("OC-14","On the Mac: a web-group search with site_set v1_docs returns results through the Vertex engine with the owner's Google sign-in; doctor shows the sign-in ok","FR-SRC-19, FR-SRC-23, FR-HLTH-25","M1"),
]

def latest(paths):
    best={}
    for f in paths:
        m=re.match(r"(.*)-v(\d+)\.md$", f)
        if not m: continue
        base,n=m.group(1),int(m.group(2))
        if base not in best or n>best[base][0]: best[base]=(n,f)
    return [f for n,f in best.values()]

def frs_in_prd():
    ids=set()
    for f in latest(glob.glob(str(ROOT/'docs/prd/**/*.md'),recursive=True)):
        body=open(f).read().split("## Changes from v1")[0] + "".join(open(f).read().split("## Changes from v1")[1:])
        ids|=set(re.findall(r'\b(FR-[A-Z]+-\d\d|NFR-\d\d)\b',body))
    return ids

def split(s): return [x.strip() for x in s.split(',') if x.strip()]

def render():
    out=[]
    areas=[("PLAT","Platform"),("SEC","Security"),("SRC","Sources"),("SRCH","Search and identity"),("CACHE","Retrieval and cache"),("HLTH","Health and credentials"),("UI","Local UI"),("MIG","Migration")]
    out.append("## 4. Acceptance test catalog\n")
    out.append("Levels: unit (no I/O beyond temp files), integration (several components, fakes for every external system), contract (through an in-memory MCP client), live (opt-in, real upstreams).\n")
    for code,name in areas:
        rows=[x for x in T if x[0].startswith(f"AT-{code}-")]
        rows.sort(key=lambda x:int(x[0].rsplit('-',1)[1]))
        out.append(f"### 4.{areas.index((code,name))+1} {name} (AT-{code})\n")
        out.append("| ID | Test | Verifies | Level | Milestone | Unit |")
        out.append("|---|---|---|---|---|---|")
        for i,title,fr,lv,ms,u in rows:
            out.append(f"| {i} | {title} | {fr} | {lv} | {ms} | {u or 'later'} |")
        out.append("")
    # traceability
    fr_all=sorted(frs_in_prd(), key=lambda s:(s.split('-')[0]!='NFR', s))
    m={f:[] for f in fr_all}
    for i,title,fr,lv,ms,u in T:
        for f in split(fr):
            if f in m: m[f].append(i)
    for i,title,fr,ms in OWNER:
        for f in split(fr):
            if f in m: m[f].append(i)
    out.append("## 5. Traceability matrix\n")
    out.append("Every requirement in the PRD set and the tests or owner checks that verify it. Generated by `tools/gen_test_plan.py`; a requirement with no test fails generation.\n")
    out.append("| Requirement | Verified by |")
    out.append("|---|---|")
    missing=[]
    for f in fr_all:
        v=m[f]
        if not v: missing.append(f)
        out.append(f"| {f} | {', '.join(v) if v else '**none**'} |")
    out.append("")
    # owner checks
    out.append("## 6. Owner and live check register\n")
    out.append("| ID | Check | Verifies | Milestone |")
    out.append("|---|---|---|---|")
    for i,c,f,ms in OWNER: out.append(f"| {i} | {c} | {f} | {ms} |")
    out.append("")
    # appendix A
    out.append("## Appendix A. M0 work units and their acceptance tests\n")
    out.append("The ECC plan (`.orchestration/plan-m0.json`) is generated from this table and LLD section 12.3.\n")
    out.append("| Unit | Acceptance tests |")
    out.append("|---|---|")
    units=sorted({x[5] for x in T if x[5]})
    for u in units:
        out.append(f"| {u} | {', '.join(x[0] for x in T if x[5]==u)} |")
    out.append("")
    return "\n".join(out), missing

if __name__=="__main__":
    body,missing=render()
    head=open(ROOT/'docs/test-plan/_plan_head.md').read()
    tail=open(ROOT/'docs/test-plan/_plan_tail.md').read()
    text=head.rstrip()+"\n\n"+body+"\n"+tail.lstrip()
    target=ROOT/'docs/test-plan/TEST-PLAN-v3.md'
    if "--check" in sys.argv:
        if not target.exists() or target.read_text()!=text:
            print("TEST-PLAN-v3.md is stale; run tools/gen_test_plan.py"); sys.exit(1)
    else:
        target.write_text(text)
    ids=[x[0] for x in T]
    dup={i for i in ids if ids.count(i)>1}
    print("tests",len(T),"owner checks",len(OWNER),"dups",dup,"untested",missing)
    if dup or missing: sys.exit(1)

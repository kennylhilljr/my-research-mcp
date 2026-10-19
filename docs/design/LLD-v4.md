# Research MCP v2: Low-Level Design (v4)

- **Date:** 2026-10-19
- **Requirements:** [PRD v4](../prd/PRD-v4.md); **shape:** [HLD v3](HLD-v3.md); **tests:** [TEST-PLAN v3](../test-plan/TEST-PLAN-v3.md); supersedes [LLD v3](LLD-v3.md)
- This document owns names: modules, classes, functions, tables, columns, settings keys, Keychain items, routes and the work breakdown. Code follows these names; changes to them come through a new version of this document.

## Changes from v3

Three M1 sources in a new `reference` group: `loc.py`, `open_library.py`, `wikipedia.py` (layout in 1; M1 outline in 12.4). Their identifiers are canonical URLs (`https://www.loc.gov/item/<id>/`, `https://openlibrary.org/works/<OLID>`, `https://en.wikipedia.org/wiki/<Title>`), so `core/ids` (M0-02) gains no new scheme; ISBN lookup goes through `open_library` search. `reference` is not in `federation.default_groups`. M0 is unchanged; the running M0 plan still cites LLD v2.

## Earlier changes (v3)

Owner decisions of 2026-10-19, second round ([ADR 0012](../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md)). All of it lands in M1 or later; **sections 1 to 6 as used by M0, and the M0 work breakdown (12.3), are unchanged.** The running M0 plan (`.orchestration/plan-m0.json`) still cites LLD v2 and TEST-PLAN v2, whose M0 content is identical to this version.

- Four web-search sources in a new `web` group, a Google sign-in provider, and the site-set, docs-site and fallback design (new section 5.5; layout in 1).
- Settings: `web.*`, `site_sets.*`, web caps, Vertex instances, Programmable Search engine id (2).
- Keychain names `BRAVE_SEARCH_API_KEY` and `SERPAPI_API_KEY`; the Google sign-in backend (3.1, 3.1.1).
- `search` gains `site_set` in M1 (7.2); federation handles the `web` group (7.1).
- Credential validation for the Google sign-in, SerpAPI and Brave; the Developer Knowledge probe query is neutral (10.3).
- `gcp` extra (12.1); M1 outline (12.4).

## Earlier changes (v2)

Owner decisions of 2026-10-19 ([ADR 0011](../adr/0011-archive-keeps-text-searchable-120-day-retention.md)):

- `cache.retention_days` is **120** (section 2; transitions in 9.1, 9.5 and 9.6).
- Archiving removes only the cached file; extraction, chunks, FTS rows and embeddings stay, so archived documents stay searchable and readable (9.3). `search_cache` gains a `states` filter (7.2).
- New archive rebuild job and CLI command (9.7, 12.1). Backups move to 9.8.
- The M0 work breakdown (12.3) is unchanged except that M0-04 implements the new retention default.

## 1. Conventions and layout

- Python 3.12 (uv-managed interpreter, which bundles a current SQLite), `uv`, `src/` layout, package `research_mcp`, version `3.0.0`.
- Typing: mypy strict on `src/`; Pydantic v2 models for everything that crosses a module boundary or the MCP boundary.
- Async: `anyio`; HTTP with `httpx.AsyncClient`; SQLite with `aiosqlite` through the store classes only.
- Time: UTC everywhere (`datetime` with `tzinfo=UTC`), stored as ISO 8601 text; the scheduler converts to local time for 09:00 and quiet hours.
- IDs: ULIDs for internal rows (`works.work_id`, `documents.doc_id`, jobs, batches).
- Tests: pytest with `--import-mode=importlib`; test folders have no `__init__.py`; shared test helpers live in the package `research_mcp.testing` so tests import them by absolute name.
- No em dashes or en dashes in code comments, docs or UI strings.

```
src/research_mcp/
  __init__.py  version.py
  cli.py                      # research-mcp: serve | stdio | doctor | ui | sources | config | install | upgrade | secrets | import-legacy | archive
  daemon.py                   # research-mcpd entry: settings -> build_app -> uvicorn on 127.0.0.1 (access_log off)
  app.py                      # build_app(settings) -> Starlette app (mounts /mcp, /ui, /healthz, /readyz, /api)
  shim.py                     # stdio <-> streamable HTTP relay
  settings.py                 # Settings, SourceSettings, paths
  core/      ids.py models.py specs.py errors.py context.py envelope.py budget.py timeutil.py
  platform/
    secrets.py                # SecretRef, Secret, SecretMeta, SecretProvider, KeychainProvider, FakeProvider
    redact.py                 # Redactor (handler filter + str API)
    logging.py                # configure_logging(settings)
    http.py                   # HttpPort, HttpClient (httpx), CredentialResolver, CallSink, PolicyResolver
    google_adc.py             # GoogleAdcProvider: Google sign-in access tokens via google-auth (M1, extra gcp)
    auth.py                   # daemon token: mint, compare (hmac.compare_digest), HKDF cursor key, UI one-time tokens
    download.py               # DownloadPolicy, Downloader, Resolver, PinnedTransport
    ratelimit.py              # TokenBucket, ConcurrencyGate, RateRegistry
    mcp_client.py             # McpUpstreamPort (MCP client over the shared HTTP client)
    stores.py                 # Database (aiosqlite), Migrator, StateStore, CacheStore
    migrations/state/0001_init.sql ...   migrations/cache/0001_init.sql ...
    workers.py                # WorkerRunner (one subprocess per task) and worker_entry
    jobs.py                   # JobService, Job, JobKind
    scheduler.py              # Scheduler (wall-clock, catches up missed runs)
  sources/
    base.py                   # SourceSpec, Capability, SourceAdapter, SourceContext
    registry.py               # SourceRegistry, Selected
    mcp_upstream.py           # UpstreamMcpAdapter base
    arxiv.py crossref.py openalex.py semantic_scholar.py datacite.py core_ac.py unpaywall.py
    openaire.py doaj.py zenodo.py hal.py dblp.py orcid.py ads.py lens.py
    osf.py biorxiv.py medrxiv.py ssrn.py hf_papers.py
    europe_pmc.py pubmed.py clinical_trials.py
    dspace.py                 # one adapter, instances from config
    ietf.py nist.py nvd.py aws_knowledge.py ms_learn.py google_devknowledge.py docs_site.py
    vertex_search.py brave_search.py serpapi.py google_pse.py    # group "web" (5.5)
    loc.py open_library.py wikipedia.py                       # group "reference"
    sitequery.py              # pure helpers: site_set -> provider query strings and batches
    github.py opencitations.py crossref_updates.py eric.py
  services/
    federation.py works.py citations.py cite.py integrity.py
    cache.py lifecycle.py archive.py extract.py chunking.py embeddings.py
    health.py credentials.py notify.py disk.py maintenance.py backup.py legacy_import.py
  mcp_app/
    server.py                 # build_mcp(services) -> FastMCP; instructions text
    tools_discovery.py tools_library.py tools_review.py tools_ops.py
    resources.py prompts.py
  ui/
    routes.py auth.py csrf.py
    templates/*.html  static/htmx.min.js  static/app.css
  testing/                    # importable fakes for tests: clock.py adapters.py launchctl.py notifier.py
  packaging/launchd/          # *.plist.template (package data, so `research-mcp install` finds them in an installed wheel)
tests/
  unit/ ...   sources/<id>/fixtures/ + test_<id>.py   sources/test_conformance.py
  services/   contract/ (in-memory MCP client)   ui/   security/   live/ (opt-in)
tools/ci.sh  tools/gen_inventory.py  tools/gen_test_plan.py  tools/gen_m0_plan.py
```

## 2. Settings and paths

`settings.Settings` (pydantic-settings), loaded from `~/.config/research-mcp/config.toml`, then `RESEARCH_MCP_*` environment overrides (nested with `__`).

| Key | Default | Notes |
|---|---|---|
| `server.host` | `127.0.0.1` | Validation rejects any non-loopback value. |
| `server.port` | `7319` | MCP at `/mcp`, UI at `/ui`. |
| `server.token` | `keychain:research-mcp/DAEMON_TOKEN` | Bearer for the shim and API. |
| `paths.state_dir` | `~/Library/Application Support/research-mcp` | `state.db`, `backups/`, `imports/` |
| `paths.data_dir` | `~/Library/Application Support/research-mcp/cache` | `cache.db`, `files/`, `trash/`, `tmp/` (not in `~/Library/Caches`, which macOS and cleaners may purge) |
| `paths.model_cache_dir` | `~/Library/Caches/research-mcp/models` | Embedding model files only (re-downloadable) |
| `paths.log_dir` | `~/Library/Logs/research-mcp` | |
| `contact.email` | none | Crossref `mailto`, Unpaywall `email`, user agent. Placeholder domains (`example.com`, `example.org`, `test`, `invalid`) are rejected. If unset, sources with `needs_contact` are `unconfigured`; the daemon still starts. |
| `limits.response_bytes` | `65536` | Envelope budget |
| `limits.download_bytes` | `52428800` | |
| `limits.pdf_pages` | `500` | |
| `limits.chunk_hard_cap_chars` | `4000` | |
| `federation.deadline_s` | `8.0` | |
| `federation.default_groups` | `["scholarly", "preprints"]` | |
| `cache.retention_days` | `120` | Fixed from fetch (ADR 0011) |
| `cache.review_lead_days` | `3` | |
| `cache.review_time_local` | `"09:00"` | |
| `cache.batch_open_hours` | `24` | Unanswered items become `kept` when the batch closes |
| `cache.reask_days` | `7` | |
| `cache.trash_days` | `7` | |
| `archive.target` | `auto` | `auto` finds the single `~/Library/CloudStorage/GoogleDrive-*/My Drive`; else an absolute path |
| `archive.confirmed_path` | none | Set when the owner confirms the detected target in the UI or with `config set`; archiving to `auto` waits for this confirmation |
| `archive.subfolder` | `Research Archive/{year}` | |
| `archive.fallback` | `~/Research Archive/{year}` | |
| `notify.macos` | `true` | `terminal-notifier` if present, else `osascript` (no click-through) |
| `notify.webhook_url` | none | OpenClaw inbox (open decision O5); any token goes in Keychain `NOTIFY_WEBHOOK_TOKEN`, never in the URL |
| `notify.quiet_hours` | `"21:00-08:00"` | |
| `disk.cache_warn_bytes` | `5368709120` | |
| `disk.free_warn_bytes` / `free_crit_bytes` | `16106127360` / `5368709120` | |
| `backup.keep` | `7` | Nightly copies of `state.db`, `cache.db` and `config.toml` |
| `sources.<id>.enabled` | spec default | |
| `sources.<id>.budget_cap` | none (`100` for `web` sources) | Daily call cap for metered sources (UI Quota page); resets at local midnight |
| `sources.vertex_<name>` | none | `{ instance_of = "vertex_search", project = "...", location = "global", engine_id = "...", title = "..." }`; one per Vertex AI Search engine (5.5) |
| `sources.google_pse.engine_id` | none | Programmable Search engine id (v1 `GOOGLE_PSE_CX`); not a secret |
| `web.strategy` | `"fallback"` | `fallback` or `all` (5.5) |
| `web.order` | `["vertex_*", "brave_search", "serpapi", "google_pse"]` | `vertex_*` expands to the configured Vertex instances in name order |
| `site_sets.<name>` | `v1_docs` (5.5) | A list of domains; names match `[a-z0-9_]{1,40}` |
| `sources.<id>.<field>` | per spec | For example `sources.dspace_penn.base_url` |
| `credentials.<NAME>.rotate_by` | none | Optional override |

Directories are created at daemon start with mode `0700`.

## 3. Platform

### 3.1 Secrets

```python
@dataclass(frozen=True)
class SecretRef:            # parsed from "keychain:research-mcp/CORE_API_KEY" or "env:NAME"
    backend: Literal["keychain", "env"]
    name: str               # CORE_API_KEY
    service: str            # research-mcp/CORE_API_KEY

@dataclass(frozen=True)
class SecretMeta: name: str; modified_at: datetime | None

class Secret:
    def __init__(self, ref: SecretRef, value: str): ...
    def reveal(self) -> str: ...            # called only in platform/http.py, platform/mcp_client.py and platform/auth.py
    @property
    def fingerprint(self) -> str: ...       # sha256(value)[:8]
    def __repr__(self) -> str: return f"Secret(name={self.ref.name}, fp={self.fingerprint})"
    __str__ = __repr__

class SecretState(StrEnum): OK="ok"; MISSING="missing"; LOCKED="keychain_locked"; ERROR="error"

class SecretProvider(Protocol):
    def get(self, ref: SecretRef) -> tuple[SecretState, Secret | None]: ...
    def metadata(self, ref: SecretRef) -> SecretMeta | None: ...   # no value
    def set(self, ref: SecretRef, value: str) -> None: ...          # value never in argv

class KeychainProvider:
    def __init__(self, user: str, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run): ...
class FakeProvider: ...      # tests; also records every argv it would have used

class SecretCache:           # what the daemon uses; implements CredentialResolver with a source->names map
    def __init__(self, provider: SecretProvider, refs: Mapping[str, SecretRef]): ...
    def load(self) -> None: ...
    def get(self, name: str) -> Secret | None: ...
    def state(self, name: str) -> SecretState: ...
    def reload(self) -> list[str]: ...      # names whose fingerprint changed
```

- **Read:** `/usr/bin/security find-generic-password -s <service> -a <user> -w`, run with a 5 s timeout.
  - Exit 44 (not found) maps to `missing`.
  - Exit 36 or 51, or "User interaction is not allowed", maps to `keychain_locked`.
  - Anything else maps to `error`.
  - stderr text is never logged or returned.
- **Metadata:** the same command without `-w`; only the `mdat` attribute is parsed.
- **Write:** `/usr/bin/security -i` with `add-generic-password -U -s <service> -a <user> -w <value>` written to stdin, so the value never appears in a process argument list. Values are checked for printable characters first, so `security -w` never returns a hex dump.
- **Keychain items:** service `research-mcp/<NAME>`, account `$USER`. The names are:
  - `DAEMON_TOKEN`, `NOTIFY_WEBHOOK_TOKEN`
  - `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `CORE_API_KEY`, `GOOGLE_DEVKNOWLEDGE_API_KEY`, `GITHUB_TOKEN`
  - `ZENODO_TOKEN`, `NCBI_API_KEY`, `NVD_API_KEY`, `ADS_API_TOKEN`, `LENS_API_TOKEN`, `OPENCITATIONS_TOKEN`
  - `BRAVE_SEARCH_API_KEY`, `SERPAPI_API_KEY` (M1). `GOOGLE_DEVKNOWLEDGE_API_KEY` is shared by `google_devknowledge` and `google_pse`, as in v1; each source's `origins` limit where it is sent.
- **Cursor signing key:** HKDF-SHA256 over `DAEMON_TOKEN` with info `research-mcp cursor v1`. No separate secret is stored.
- **ACL behavior:** items written by `/usr/bin/security` trust that binary, so reads by the daemon do not prompt, even after Python upgrades.

### 3.1.1 Google sign-in (M1)

`vertex_search` does not use a Keychain item. `SecretRef` gains the backend `gcloud_adc` (reference text `gcloud_adc:GOOGLE_SIGNIN`), resolved by `platform/google_adc.py`:

```python
class GoogleAdcProvider:                     # implements SecretProvider for backend "gcloud_adc"; extra gcp
    def __init__(self, loader: Callable[[], tuple[Credentials, str | None]] = default_loader,
                 sink: CallSink | None = None, clock: Clock = SYSTEM_CLOCK): ...
    def get(self, ref: SecretRef) -> tuple[SecretState, Secret | None]: ...   # cached token; refresh when < 5 min left
    def metadata(self, ref: SecretRef) -> SecretMeta | None: ...              # account email, token expiry; no token
    def set(self, ref: SecretRef, value: str) -> None: raise NotImplementedError   # gcloud owns the sign-in
```

- `default_loader` calls `google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])`. Loading and refreshing are blocking, so the daemon calls them through `anyio.to_thread.run_sync`, never on the event loop.
- `DefaultCredentialsError` maps to `missing`; `RefreshError` (for example `invalid_grant`, reauthentication required) maps to `invalid` (10.3). The exception text is never logged or returned.
- The refresh request goes from `google-auth` to `oauth2.googleapis.com` only; the provider records it as a `CallRecord` with `source="google_signin"`.
- The access token is wrapped in `Secret` (name `GOOGLE_SIGNIN`), held in memory, and revealed only by `platform/http.py` for origins in the Vertex spec (`https://discoveryengine.googleapis.com`), as a bearer token plus `X-Goog-User-Project: <project>`.
- v2's own code never opens, copies or writes the credential file.

### 3.2 Redaction and logging

- `Redactor` holds the set of revealed secret values (registered when loaded) and the patterns in FR-PLAT-13.
  - API: `redact(text) -> str`, plus `RedactingFilter(logging.Filter)`, which rewrites `record.msg`, `record.args` and the exception text.
- `configure_logging(settings)` is called only by `daemon.py` and `cli.py`.
  - It attaches `RedactingFilter` to **every handler**, not to a logger, so records propagated from child and third-party loggers are covered.
  - It sets the `httpx`, `httpcore`, `uvicorn.access` and `mcp` loggers to `WARNING`.
  - Handlers:
    - `RotatingFileHandler(log_dir/research-mcp.jsonl, 10 MB, 5)` with a JSON formatter;
    - `StreamHandler(stderr)` at `WARNING`.
- Log record fields are listed in FR-PLAT-41. `correlation_id` comes from a `contextvars.ContextVar` set per tool call and per job.

### 3.3 HTTP client

Policies, credentials and telemetry are injected, so the HTTP layer does not depend on the source layer:

```python
class PolicyResolver(Protocol):
    def policy(self, source: str) -> SourcePolicy: ...            # core/specs.py (section 4)
class CredentialResolver(Protocol):
    def secret_for(self, source: str) -> Secret | None: ...
class CallSink(Protocol):
    def record(self, call: CallRecord) -> None: ...               # non-blocking; buffered

class HttpPort(Protocol):
    async def get_json(self, url: str, *, source: str, params: Mapping[str, str] | None = None,
                       headers: Mapping[str, str] | None = None, max_bytes: int | None = None,
                       auth: AuthUse = AuthUse.SPEC) -> JsonValue: ...
    async def post_json(self, url: str, *, source: str, json: JsonValue, ...) -> JsonValue: ...
    async def get_text(self, url: str, *, source: str, ...) -> TextResponse: ...

class HttpClient(HttpPort):
    def __init__(self, policies: PolicyResolver, credentials: CredentialResolver, sink: CallSink,
                 clock: Clock, sleeper: Sleeper, contact_email: str | None, transport: httpx.AsyncBaseTransport | None = None): ...
```

- **Client:** one `httpx.AsyncClient` per daemon. HTTP/2 is on. Connection limits are 50 in total and 8 per host. The user agent is `research-mcp/3.0 (+mailto:<contact>)`.
- **Hosts:** a request whose host is not in `policy.hosts` fails with `blocked_by_policy`.
- **Rate limits:** each source gets a `TokenBucket(rate, burst)` and a `ConcurrencyGate(n)` from `policy.rate`. These are kept in one `RateRegistry` for the daemon, so they are global across clients. arXiv runs at 1 request per 3 s, burst 1, concurrency 1.
- **Retries:** up to 3 attempts on 429, 500, 502, 503 and 504, and on connection errors. If every attempt gets a 429, the call fails with `rate_limited` and the last `retry_after_ms`.
  - The delay is `Retry-After` when present. A delay over 60 s is not waited for; the call fails with `rate_limited` and `retry_after_ms`.
  - Without `Retry-After`, the delay is exponential from a 0.5 s base, with full jitter.
  - Other 4xx responses are not retried.
  - All waiting goes through the injected `Sleeper`, so tests never sleep for real.
- **Auth:**
  - The secret comes from `CredentialResolver`.
  - It is attached only when the request origin is in `policy.auth.origins`.
  - Placement is `header` (name from the spec), `bearer`, or `query` (parameter name from the spec).
  - Query placement is used only where the API offers nothing else, and then the URL is never logged.
- **Size:** responses are streamed; passing `max_bytes` (default from the policy) aborts the call with `too_large`.
- **Telemetry:** every attempt produces a `CallRecord` for the `CallSink`. In the daemon the sink is `StateStore.record_call`, flushed every second.
- **Errors:** the client raises `HttpError(code: ErrorCode, status: int | None, retry_after_ms: int | None, detail: str | None)`, defined in `core/errors.py`. Before the generic mapping, a non-2xx response is passed to `policy.error_classifier` when the source declares one (for example OpenAlex maps an "Insufficient budget" 429 to `budget_exhausted` with `detail="daily budget"`). The message text is generic; details go to the log through the redactor.

### 3.4 Downloader

`Downloader(resolver: Resolver, policy: DownloadPolicy, ...)`. The algorithm is a port of v1's `security.download_pdf_atomic`, with DNS pinning added:

1. Require `https`. Resolve the host through the injected `Resolver` (the system resolver in the daemon, a fake in tests). Reject private, loopback, link-local, multicast and reserved addresses, for both IPv4 and IPv6.
2. Connect through `PinnedTransport` to the **checked IP**, with SNI and the `Host` header set to the hostname. httpx never resolves the name a second time, which closes the DNS-rebinding gap.
3. Set `follow_redirects=False` and follow up to 5 redirects by hand. On every hop, repeat steps 1 and 2 and re-check the scheme and the host policy (`policy.allowed_hosts`, or `public_any`).
4. Stream into `data_dir/tmp/<ulid>.part` with a byte cap. Check `Content-Type` against `policy.media_types`, and check the first bytes: `%PDF-` for PDF; for HTML, `<` after any whitespace.
5. Run `fsync`, compute SHA-256, and move the file atomically to `data_dir/files/<sha256[:2]>/<sha256>.<ext>`. If that file already exists, reuse it.
6. Return `DownloadedFile` (section 4).

**File deletion rule:** a stored file is removed only when no `files` row with the same `sha256` belongs to a document in a non-terminal state (`cached`, `pinned`, `expiring`, `kept`), and no discard of it is still within its trash period.

### 3.5 Stores and migrations

- `Database(path)` holds one `aiosqlite` connection for writes, serialized through an `asyncio.Lock`, and a small pool for reads. Pragmas: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`.
- `Migrator` applies `migrations/<db>/NNNN_*.sql` in order.
  - Each script runs inside an explicit `BEGIN IMMEDIATE` and `COMMIT` that the Migrator issues itself. It never uses `executescript`, which commits implicitly.
  - It sets `PRAGMA user_version` and refuses to open a database whose `user_version` is newer than the newest migration.
  - At start it asserts `sqlite3.sqlite_version_info >= (3, 37, 0)`.
- Migration `.sql` files ship as package data. M0-01 configures this in `pyproject.toml`.
- `StateStore` and `CacheStore` expose typed methods only. No SQL appears outside `platform/stores.py` and the `services/*` repositories. Methods M0 needs (all defined in M0-08):
  - `StateStore.record_call(call)` (buffered) and `flush()`;
  - `job_insert(job)`, `job_update(job_id, **fields)`, `job_get(job_id)`, `job_list(state=None)`;
  - `schedule_get(job)`, `schedule_set(job, last_run_at, next_due_at)`;
  - `source_health_get(source)`, `source_health_list()`, `source_health_put(row)`;
  - `CacheStore.outbox_drain(limit) -> list[OutboxRow]` (the rest of `CacheStore` arrives in M2 as `services/*` repositories).
- **Cross-database events.** `documents.decided_*` in `cache.db` is authoritative. Each lifecycle transition also writes a row to `cache.db.outbox` in the same transaction. A drainer copies outbox rows to `state.db.review_events` and deletes them, so neither database needs a transaction that spans both.

### 3.6 Workers and jobs

`WorkerRunner` runs every CPU-heavy task in its own subprocess. `ProcessPoolExecutor` is not used, because on macOS it cannot enforce memory limits or kill a running task.

- The task is launched with `anyio.open_process([python, "-m", "research_mcp.platform.workers", <task>])`. Input goes in as JSON on stdin; the result comes back as JSON on stdout.
- In the child, `RLIMIT_CPU` is 120 s. `RLIMIT_AS` is not relied on, because macOS does not enforce it.
- The parent enforces a 180 s wall clock and samples the child's RSS every second with `psutil`. Past 2 GB, or at the timeout, it sends SIGKILL.
- A crash or kill affects only that task, which ends with code `extract_failed`.
- Tasks: `extract_pdf`, `extract_html`, `chunk`, `embed`. At most 2 run at once.

`JobService` provides `submit(kind, params) -> job_id`, `status(job_id)`, `cancel(job_id)` and `list(state)`.

- Job state lives in `state.db.jobs`.
- Progress is pushed to MCP `Context.report_progress` while the caller waits.
- Resumable job kinds store a cursor.

`Scheduler` is driven by the wall clock, not by asyncio timers, which stall while the Mac sleeps.

- Every 60 s it compares the wall clock with each job's next due time.
- A job missed because the Mac was asleep or the daemon was down runs once at start or on wake. It never runs once per missed day.
- Daily schedules:

| Job | Local time |
|---|---|
| `review` | 09:00 |
| `digest` | 08:00 |
| `backup_state` | 03:30 |
| `maintenance_daily` | 04:00 |
| `trash_purge_notice` and `trash_purge` | 10:00 |

- Interval schedules: probes at their own cadence; `disk_sample` every 15 minutes; `outbox_drain` every 5 s.

### 3.7 Errors and the envelope

```python
class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "invalid_argument"; NOT_FOUND = "not_found"; UNCONFIGURED = "unconfigured"
    AUTH_FAILED = "auth_failed"; RATE_LIMITED = "rate_limited"; UPSTREAM_ERROR = "upstream_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"; BUDGET_EXHAUSTED = "budget_exhausted"; TOO_LARGE = "too_large"
    BLOCKED_BY_POLICY = "blocked_by_policy"; DISABLED = "disabled"; EXTRACT_FAILED = "extract_failed"
    INTERNAL = "internal"

class ToolError(Exception):  code: ErrorCode; message: str; retryable: bool; correlation_id: str

class SourceStatus(BaseModel):
    source: str; state: Literal["ok","empty","timeout","rate_limited","error","unconfigured",
                                "disabled","skipped_unhealthy","skipped_budget"]
    count: int = 0; latency_ms: int | None = None; retry_after_ms: int | None = None
    error_code: ErrorCode | None = None

class Untrusted(BaseModel):  untrusted: Literal[True] = True; source: str; content: str

class ToolResult(BaseModel, Generic[T]):
    data: T; source_status: list[SourceStatus] = []; warnings: list[str] = []
    next_cursor: str | None = None; truncated: bool = False
```

**Budget.** `core.budget.fit(result, limit_bytes)` trims list items from the end, and shortens long text fields to a marker, until the JSON size fits. It then sets `truncated` and keeps the cursor.

**Cursors.** Cursors are base64url JSON with an HMAC-SHA256 tag. `core.budget` takes the key as a parameter (the daemon derives it as described in 3.1), so that agents cannot forge cursors.

`HttpError` lives in `core/errors.py` and the `correlation_id` `ContextVar` in `core/context.py` (both M0-03), so neither the platform nor the MCP layer needs to import the other.

**`@tool_boundary`** is defined in `mcp_app/server.py` (M0-14). Every MCP tool carries this one decorator. It:

- sets the correlation id;
- turns `ToolError` and `HttpError` into the error result;
- maps any other exception to `internal`, logging the traceback through the redactor;
- applies the budget.

## 4. Specs, models and the source contract

`core/specs.py` holds the pure policy types. They are shared by the HTTP layer (M0-07) and the source layer (M0-09):

```python
@dataclass(frozen=True)
class AuthSpec:
    secrets: tuple[str, ...]                 # Keychain names
    required: bool
    placement: Literal["header", "query", "bearer"]
    param: str                               # header or query name
    origins: tuple[str, ...]                 # credential attached only for these origins (scheme://host)
    signup_url: str
    validation: Literal["probe", "github_rate_limit", "header_expiry", "none"] = "probe"

@dataclass(frozen=True)
class RateSpec: rps: float; burst: int = 1; concurrency: int = 2; daily_quota: int | None = None

@dataclass(frozen=True)
class ProbeSpec: cadence_s: int; cost: Literal["free", "metered"]; description: str

ErrorClassifier = Callable[[int, bytes], tuple[ErrorCode, str | None] | None]   # status, body -> (code, detail)

@dataclass(frozen=True)
class SourcePolicy:
    source: str; hosts: frozenset[str]; auth: AuthSpec | None; rate: RateSpec
    timeout_s: float; max_bytes: int; error_classifier: ErrorClassifier | None = None
```

`core/models.py` holds the shared data types:

```python
JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
class Clock(Protocol): def now(self) -> datetime: ...           # UTC
class Sleeper(Protocol): async def sleep(self, seconds: float) -> None: ...
class AuthUse(StrEnum): SPEC="spec"; NONE="none"

from research_mcp.core.ids import Identifier                    # frozen dataclass, section 6 (re-exported)
class Author(BaseModel): name: str; family: str | None = None; orcid: str | None = None
class OaLocation(BaseModel): url: str; source: str; kind: Literal["pdf","html","landing"]
                             license: str | None = None; version: str | None = None
class Provenance(BaseModel): source: str; upstream_id: str; adapter_version: str; retrieved_at: datetime
class WorkRecord(BaseModel):
    ids: list[Identifier]; title: str; authors: list[Author] = []; year: int | None = None
    published_at: date | None = None; venue: str | None = None; work_type: str = "article"
    abstract: str | None = None; oa_locations: list[OaLocation] = []; is_retracted: bool | None = None
    extra: dict[str, JsonValue] = {}; provenance: Provenance
class SearchFilters(BaseModel):
    year_from: int | None = None; year_to: int | None = None; work_type: str | None = None
    oa_only: bool = False; provider: str | None = None; repository: str | None = None
class SearchRequest(BaseModel): query: str; filters: SearchFilters = SearchFilters(); limit: int = 10
                                cursor: str | None = None
class SearchPage(BaseModel): records: list[WorkRecord]; total: int | None = None; next_cursor: str | None = None
class FulltextCandidate(BaseModel): location: OaLocation; priority: int
class CitationPage(BaseModel): ids: list[Identifier]; records: list[WorkRecord] = []; next_cursor: str | None = None
class ProbeResult(BaseModel): ok: bool; latency_ms: int; shape_ok: bool; detail_code: str | None = None
                              quota_remaining: str | None = None; credential_expires_at: datetime | None = None
class Conflict(BaseModel): field: str; values: dict[str, JsonValue]       # source -> value
class Work(BaseModel):
    work_id: str | None = None; ids: list[Identifier]; title: str; authors: list[Author]
    year: int | None; venue: str | None; work_type: str; abstract: str | None
    oa_locations: list[OaLocation]; found_in: list[str]; fuzzy: bool = False
    conflicts: list[Conflict] = []; integrity_status: str = "unknown"; cache_state: str = "none"
class FederatedResult(BaseModel): works: list[Work]; statuses: list[SourceStatus]; next_cursor: str | None
class TextResponse(BaseModel): url: str; status: int; content_type: str; text: str
class DownloadedFile(BaseModel): sha256: str; size: int; media_type: str; storage_path: str; final_url: str
                                 http_status: int; etag: str | None; last_modified: str | None
class CallRecord(BaseModel): ts: datetime; source: str; op: str; status: int | None; error_code: str | None
                             latency_ms: int; bytes: int; rl_remaining: str | None; rl_reset: str | None
                             cred_expires_at: str | None; correlation_id: str | None; attempt: int
```

`sources/base.py` holds the source contract:

```python
class Capability(StrEnum): SEARCH="search"; GET="get"; FULLTEXT="fulltext"; CITATIONS="citations"
                           AUTHORS="authors"; UPDATES="updates"; CRAWL="crawl"

@dataclass(frozen=True)
class SourceSpec:
    id: str; title: str; group: str
    capabilities: frozenset[Capability]
    id_schemes: frozenset[str]
    hosts: frozenset[str]                    # every host the adapter may call
    auth: AuthSpec | None
    rate: RateSpec
    timeout_s: float = 5.0
    max_page_size: int = 50
    max_bytes: int = 5_000_000
    needs_contact: bool = False
    extras: frozenset[str] = frozenset()
    probe: ProbeSpec = ProbeSpec(3600, "free", "")
    enabled_by_default: bool = True
    shutdown_on: date | None = None
    docs_url: str = ""
    instance_of: str | None = None           # "dspace" for dspace_mit
    error_classifier: ErrorClassifier | None = None
    def policy(self) -> SourcePolicy: ...

class McpUpstreamPort(Protocol):              # implemented in M1 by platform/mcp_client.py
    async def call_tool(self, server: str, tool: str, arguments: Mapping[str, JsonValue], *, source: str) -> JsonValue: ...

class SourceContext:                         # given to each adapter instance
    http: HttpPort; mcp: McpUpstreamPort | None; settings: SourceSettings; clock: Clock

class SourceAdapter(Protocol):
    spec: SourceSpec
    async def search(self, req: SearchRequest) -> SearchPage: ...
    async def get(self, ident: Identifier) -> WorkRecord | None: ...
    async def fulltext_candidates(self, work: WorkRecord) -> list[FulltextCandidate]: ...
    async def citations(self, ident: Identifier, direction: Literal["citing","cited"],
                        cursor: str | None, limit: int) -> CitationPage: ...
    async def probe(self) -> ProbeResult: ...
```

Adapters parse XML with `defusedxml`. They may import `urllib.parse`, but not `urllib.request`, `http.client`, `socket`, `httpx`, `requests`, `time.sleep`, `asyncio.sleep`, or `research_mcp.platform.secrets`.

## 5. Registry, instances and testing

### 5.1 Registry

- **Built-in adapters** are discovered by scanning the `research_mcp.sources` package with `pkgutil.iter_modules`. Any module that defines a module-level `SPEC: SourceSpec` and `ADAPTER: type[SourceAdapter]` is registered. No central list is edited when a source is added.
- **Third-party adapters** can register through the entry point group `research_mcp.sources`.
- **Instances** come from settings. For example, `sources.dspace_mit = { instance_of = "dspace", base_url = "https://dspace.mit.edu/server/api", title = "DSpace@MIT" }`. The same form covers `dspace_harvard`, `dspace_cornell` and `dspace_penn`, and the `docs_site_<name>` entries with their `allowed_hosts` and `path_prefixes`. An instance's `hosts` come from its base URL.
- **Construction.** `SourceRegistry(settings, ctx_factory, *, has_credential: Callable[[str], bool], health: Callable[[str], str | None] = lambda s: None, modules: Iterable[str] | None = None, extra_adapters: Iterable[tuple[SourceSpec, type[SourceAdapter]]] = ())`. Tests pass `modules=[]` and `extra_adapters` from `research_mcp.testing.adapters`; the daemon passes the defaults. Credential presence and health come in as callables, so nothing under `sources/` imports the secrets or health modules.
- **Selection.** `SourceRegistry.select(groups, capability, filters, explicit) -> list[Selected]` combines the enabled flags, credential presence, contact presence, extras and current health state. `Selected` holds the `source`, the `adapter`, and a `skip: SourceStatus | None`.
- **Policies.** The registry implements `PolicyResolver` from each spec's `policy()`.

### 5.2 Fixtures and conformance

Each source has a fixtures folder, `tests/sources/<id>/fixtures/`, with these fixtures:

| Fixture | Contents |
|---|---|
| `search_ok`, `search_empty`, `get_ok` | Normal responses |
| `err_429` | Status and headers, as JSON |
| `err_5xx` | JSON |
| `malformed` | A broken body |
| `oversize.marker` | A marker only; the test generates the large body |

Body fixtures use the upstream's format: `.json` for JSON APIs, `.xml` for Atom (arXiv).

`tests/sources/test_conformance.py` is parametrized over `SourceRegistry.all()`. It serves the fixtures through an `httpx.MockTransport`, uses a fake `Sleeper` and a `FakeClock`, and checks:

1. `search_ok` maps to at least one `WorkRecord` with a normalized identifier and provenance.
2. `search_empty` returns an empty page, not an error.
3. 429 raises `HttpError(rate_limited)` with `retry_after_ms`, and the fake sleeper records the wait.
4. 5xx raises `upstream_error` once the retry budget is spent.
5. A malformed body raises `upstream_error`, never `KeyError`, `TypeError` or `ValueError`.
6. An oversize body raises `too_large` before the whole body is read.
7. Every request goes to a host in `spec.hosts`.
8. `probe` returns `ok=True, shape_ok=True` against `get_ok`, and `shape_ok=False` against `malformed`.

Run a single source with `-k <id>`. The fake adapter in `research_mcp.testing.adapters` carries its own seven fixtures in memory and is registered through `extra_adapters`, so the suite runs in M0-09 before any real adapter exists.

### 5.3 Live check

`research-mcp sources check --live [--id X] [--refresh-fixtures]` calls each enabled source once through the daemon's client. With `--refresh-fixtures`, it writes new fixtures to `tests/sources/<id>/fixtures/_review/`. It never overwrites the committed fixtures.

### 5.4 New-source checklist (definition of done)

1. Add `src/research_mcp/sources/<id>.py` with `SPEC` and `ADAPTER`. No other source file changes.
2. Discovery is automatic.
3. Add a fixtures folder with the seven fixtures. The conformance suite passes with `-k <id>`.
4. Add unit tests for any source-specific mapping.
5. If the source needs a credential, add the Keychain name to section 3.1 in the next version of this document, and put the signup URL in the spec.
6. Regenerate the inventory (`tools/gen_inventory.py`). In milestone plans, one closing unit does this for all new sources.

### 5.5 Site sets, docs sites and web search (M1)

**Default data.** `src/research_mcp/packaging/defaults.toml` (package data) holds data the owner can override in `config.toml`. It carries every v1 endpoint forward (FR-SRC-17):

- `site_sets.v1_docs`: v1's docs-domain list, verbatim: `keycloak.org`, `ory.sh`, `supertokens.com`, `authelia.com`, `goauthentik.io`, `zitadel.com`, `logto.io`, `casdoor.org`, `authgear.com`, `kanidm.github.io`, `freeipa.org`, `syncope.apache.org`, `openpolicyagent.org`, `cerbos.dev`, `authzed.com`, `casbin.org`, `permify.co`, `topaz.sh`, `warrant.dev`, `pomerium.com`, `developer.hashicorp.com`, `infisical.com`, `webauthn.guide`, `jwt.io`, `datatracker.ietf.org`, `zanzibar.academy`.
- `docs_site_*` instances for v1's six crawl projects, with the same seeds and filters:

| Instance | Seeds | Follow links | Path prefixes |
|---|---|---|---|
| `docs_site_keycloak` | sitemap `https://www.keycloak.org/sitemap.xml` | sitemap | `/docs/`, `/securing-apps/`, `/guides/` |
| `docs_site_ory` | sitemap `https://www.ory.sh/sitemap.xml` | sitemap | `/docs/` |
| `docs_site_opa` | sitemap `https://www.openpolicyagent.org/sitemap.xml` | sitemap | `/docs/` |
| `docs_site_vault` | `https://developer.hashicorp.com/vault/docs` | yes | `/vault/docs` |
| `docs_site_syncope` | the 4.1 and 4.0 reference guide and getting-started pages | no | (the seed pages only) |
| `docs_site_freeipa` | `https://www.freeipa.org/page/Documentation.html` | yes | `/page/` |

A `docs_site` instance has `allowed_hosts`, `path_prefixes`, and either `sitemap` or `seed_urls` with `follow_links`. v1 matched filters as URL substrings; v2 matches the parsed host against `allowed_hosts` and the parsed path against `path_prefixes` (FR-SRC-15).

**Web sources.** All four have `group="web"`, `enabled_by_default=False` (enabled once settings and credential are present), `probe.cost="metered"` where no free probe exists, `rate.daily_quota` from `budget_cap`, and return `work_type="webpage"` records with the URL as identifier and the snippet as an untrusted abstract.

| Source | Endpoint | Auth | Free probe and quota |
|---|---|---|---|
| `vertex_search` (instances `vertex_<name>`) | `POST https://discoveryengine.googleapis.com/v1/projects/{project}/locations/{location}/collections/default_collection/engines/{engine_id}/servingConfigs/default_search:search` with `{"query", "pageSize", "pageToken"}` | Google sign-in (3.1.1) | `GET .../engines/{engine_id}` every 6 h (no query cost) |
| `brave_search` | `GET https://api.search.brave.com/res/v1/web/search?q=&count=` | `X-Subscription-Token` header | none free: one query every 24 h; rate-limit headers parsed passively on every call |
| `serpapi` | `GET https://serpapi.com/search.json?engine=google&q=&num=` | `api_key` query parameter (URL never logged) | `GET https://serpapi.com/account.json` (free; gives searches left) every 6 h |
| `google_pse` | `GET https://www.googleapis.com/customsearch/v1?cx=&q=&num=` | `x-goog-api-key` header | none free: one query every 24 h; `shutdown_on = 2027-01-01` |

**Site sets in queries** (`sources/sitequery.py`, pure functions):

- `site_query(query, domains) -> str` builds `(<query>) (site:a OR site:b ...)`, as v1 did.
- `site_batches(query, domains, max_chars, max_batches) -> list[str]` splits the domains so each query fits; the domains the query names come first (v1's ranking). Brave uses `max_chars=380`, `max_batches=3`; SerpAPI and Programmable Search use one query (`max_batches=1`) and report `truncated` when domains are dropped.
- Vertex ignores `site_query`; when `site_set` is given, results are filtered after the call by host.

**Federation of the `web` group** (`FederationService`, 7.1):

- `auto` selection never includes `web`, because `federation.default_groups` excludes it.
- When a caller names the group (or more than one web source) and `web.strategy == "fallback"`, the web sources run one at a time in `web.order`, skipping any whose status is `disabled`, `unconfigured`, `budget_exhausted`, `rate_limited` or `down`. The first that returns at least one result without error ends the chain; the others report `state="not_needed"`. Non-web sources in the same call still fan out in parallel, and the web chain shares the overall deadline.
- With `strategy == "all"`, web sources fan out like any other group.
- Each call to a web source counts against its cap in `StateStore` (`quota_used` in `source_health`); at the cap the source reports `budget_exhausted(reset=next local midnight)`.

## 6. Identity

`core/ids.py` contains pure functions with no I/O. It raises `ValueError` subclasses; `@tool_boundary` maps them to `invalid_argument`.

| Function | Rule |
|---|---|
| `normalize_doi(s)` | Strip `doi:`, `https://doi.org/`, `http://dx.doi.org/`; lowercase; trim trailing punctuation. The result must match `^10\.\d{4,9}/\S+$`. |
| `normalize_arxiv(s)` | Strip `arxiv:`, `arXiv:`, `https://arxiv.org/abs/`, `/pdf/` and `.pdf`, then split off the `vN` version. New style: `^\d{4}\.\d{4,5}$`. Old style: `^[a-z\-]+(\.[A-Z]{2})?/\d{7}$`. Returns `(id, version)`. |
| `normalize_pmid`, `normalize_pmcid` | Digits only; a PMCID keeps its `PMC` prefix. |
| `normalize_openalex` | `W\d+`, taken from any OpenAlex URL form. |
| `normalize_s2`, `normalize_core`, `normalize_nct`, `normalize_rfc` | Canonical forms; `rfc` is integer text. |
| `normalize_handle`, `normalize_dspace_uuid` | A handle becomes `prefix/suffix`; a UUID is lowercased. |
| `normalize_github` | `owner/repo`, lowercase, from `github:` or a `github.com` URL. |
| `normalize_url` | Lowercase the scheme and host; drop default ports, fragments and tracking parameters; keep the path's case. |
| `parse_any(s) -> Identifier` | Detects the scheme from prefixes, URL hosts and shapes, and raises `IdentifierError` otherwise. Strings shaped like file names (`doi_10.1145_x`, `core_123`, anything ending `.pdf` without a URL scheme) are rejected. |
| `title_key(title)` | Unicode NFKC, casefold, then strip punctuation and stop words and collapse spaces. |

`ids.py` defines its own `Identifier` dataclass, re-exported by `core/models.py`. This keeps M0-02 independent of M0-03's Pydantic models.

A bare DSpace UUID resolves against every DSpace instance concurrently. A bare handle prefix picks the matching instance.

`services/works.py` holds grouping and merging:

- **`group(records) -> list[Group]`** runs union-find over records, keyed by every normalized identifier. Groups that share no identifier are then merged when `title_key`, `year` and the first author's family name all match. The merged group is marked `fuzzy=True`.
- **`merge(group) -> Work`** takes bibliographic fields by source priority: `crossref`, then `openalex`, then `datacite`, then `semantic_scholar`, then the rest. It unions identifiers and OA locations, builds `found_in` from the provenance, and records disagreements in `Work.conflicts`.

## 7. Services and the MCP surface

### 7.1 Federation

`FederationService.search(req, sources, groups) -> FederatedResult`:

1. Call `selected = registry.select(...)`. Statuses for skipped sources are created immediately. (From M1, `web` sources follow the fallback rules in 5.5.)
2. Inside `async with anyio.create_task_group()` with `anyio.move_on_after(deadline)`, run one task per source with `fail_after(spec.timeout_s)`. The per-source limit is `min(per_source_limit, spec.max_page_size)`.
3. Decode the combined cursor to get each source's own cursor. Sources whose cursor is exhausted are skipped with `state="empty"`.
4. Group and merge (`services/works.py`), then rank by reciprocal rank fusion with k = 60, plus 0.1 for each additional source. Fit the result to the budget and encode the combined cursor.

### 7.2 Tool catalog

All tools return `ToolResult[...]` and carry annotations. In the table, "RO" means read-only and "OW" means open world. 17 tools in total.

| Tool | Signature (bounds) | Service | Annotations | M |
|---|---|---|---|---|
| `search` | `query: str (1..500), sources: Literal["auto"] or list[str] (<=20) = "auto", groups: list[str] = [], site_set: str = None (M1; a configured site set), year_from: int (1800..2100) = None, year_to = None, work_type: Literal[...] = None, oa_only: bool = False, provider: str = None, repository: str = None, limit: int (1..50) = 20, per_source_limit: int (1..25) = 10, cursor: str = None, detail: Literal["compact","full"] = "compact"` | federation | RO, OW | M0 |
| `get_work` | `id: str (1..300)` | works | RO, OW | M0 |
| `list_sources` | `group: str = None, state: str = None` | registry + health | RO | M0 |
| `citations` | `id: str, direction: Literal["citing","cited","both"] = "both", limit: int (1..100) = 25, cursor: str = None` | citations | RO, OW | M1 |
| `authors` | `query: str = None, orcid: str = None, limit: int (1..25) = 10` | works | RO, OW | M1 |
| `cite` | `ids: list[str] (1..100) = [], collection: str = None, format: Literal["bibtex","csl-json","ris","text"] = "bibtex", style: Literal["apa","ieee","chicago-author-date","mla","harvard"] = "apa"` | cite | RO, OW | M1 |
| `check_integrity` | `ids: list[str] (1..50) or "cache"` | integrity | RO, OW | M1 |
| `ops_status` | none | health | RO | M1 |
| `fetch` | `id_or_url: str, prefer: list[str] = [], pin: bool = False` | cache | not RO, OW, idempotent | M2 |
| `read` | `doc_id: str, pages: str = None, section: str = None, chunks: str = None, max_chars: int (500..20000) = 8000, cursor: str = None` | cache | RO | M2 |
| `search_cache` | `query: str, mode: Literal["hybrid","keyword","semantic"] = "hybrid", doc_ids: list[str] = [], collection: str = None, states: list[Literal["cached","pinned","expiring","kept","archived"]] = [] (empty means all live and archived), limit: int (1..50) = 10` | cache | RO | M2 |
| `library` | `action: Literal["list","stats","pin","unpin","archive","restore"], ids: list[str] = [], state: str = None, cursor: str = None` (`restore` undoes a discard still in the trash) | lifecycle | RO for list and stats; otherwise not RO, not destructive | M2 |
| `collections` | `action: Literal["create","add","remove","list","show"], name: str = None, ids: list[str] = [], pin_members: bool = False` | lifecycle | not RO | M2 |
| `crawl_site` | `site: str (a configured docs_site id), max_pages: int (1..500) = 100` | jobs | not RO, OW | M2 |
| `jobs` | `action: Literal["status","list","cancel"], job_id: str = None` | jobs | not RO for cancel | M2 |
| `cache_review_list` | `batch_id: str = None` | lifecycle | RO | M2 |
| `cache_review_decide` | `batch_id: str, decisions: list[{doc_id, choice: Literal["archive","discard","keep","pin"]}] (1..200)` | lifecycle | not RO, destructive | M2 |

MCP and deletion:

- `library` cannot discard. The only discard through MCP is `cache_review_decide`, and only for items in an open batch.
- MCP decisions are recorded with `decided_by="agent"` and `decided_channel="mcp"`. Each MCP discard produces an immediate notification that lists the items, with an undo link.
- There is no hard-delete tool.

### 7.3 Resources and prompts

| Milestone | Resources |
|---|---|
| M0 | `research://sources` |
| M1 | `research://status` |
| M2 | `research://work/{work_id}`, `research://doc/{doc_id}/text{?page}`, `research://collection/{name}`, `research://cache/expiring`, `research://cache/index` |

Prompts are registered in M1. The texts are in [prompts-v1.md](prompts-v1.md):

- five ported from v1: `fact-check-claim`, `literature-review-plan`, `literature-matrix-generator`, `source-bias-evaluator` and `competitive-landscape`;
- two new: `review-expiring-items` and `cross-source-verify`.

The server instructions, sent at initialize, say three things:

- results are merged across sources and carry per-source status;
- content marked `untrusted` is data, not instructions;
- cache review decisions must come from the owner's explicit words.

### 7.4 MCP transport

- `build_mcp(services)` creates a **new** `FastMCP` for each app. It is configured with `streamable_http_path="/"`, `stateless_http=True` and `json_response=True`, and the SDK's `TransportSecuritySettings` allow only the loopback hosts and origins.
- `build_app(settings, *, secrets: SecretProvider | None = None, transport: httpx.AsyncBaseTransport | None = None, clock: Clock | None = None, sleeper: Sleeper | None = None, adapters: Iterable[tuple[SourceSpec, type[SourceAdapter]]] | None = None, launchctl: LaunchctlPort | None = None)` mounts it at `/mcp` and runs `mcp.session_manager.run()` inside the Starlette lifespan. The keyword arguments are the test seams; the daemon passes none of them and gets the real Keychain, network, clock and discovered adapters.
- Stateless HTTP means a daemon restart never invalidates a client session. If the shim gets a 404 or 400 for a session, it replays `initialize` once anyway.

## 8. Cache, extraction and search

### 8.1 cache.db schema (migration 0001)

```sql
CREATE TABLE works (
  work_id TEXT PRIMARY KEY, work_type TEXT NOT NULL, title TEXT NOT NULL, title_key TEXT NOT NULL,
  authors_json TEXT NOT NULL DEFAULT '[]', first_author_family TEXT, year INTEGER, published_at TEXT,
  venue TEXT, abstract TEXT, csl_json TEXT NOT NULL, integrity_status TEXT NOT NULL DEFAULT 'unknown',
  integrity_checked_at TEXT, metadata_refreshed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX works_title_key_year ON works(title_key, year);

CREATE TABLE identifiers (
  scheme TEXT NOT NULL, value TEXT NOT NULL, raw TEXT NOT NULL,
  work_id TEXT NOT NULL REFERENCES works(work_id) ON DELETE CASCADE,
  source TEXT NOT NULL, first_seen_at TEXT NOT NULL,
  PRIMARY KEY (scheme, value));
CREATE INDEX identifiers_work ON identifiers(work_id);

CREATE TABLE source_records (
  source_record_id TEXT PRIMARY KEY, work_id TEXT REFERENCES works(work_id) ON DELETE SET NULL,
  source TEXT NOT NULL, upstream_id TEXT NOT NULL, adapter_version TEXT NOT NULL,
  retrieved_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL, payload_json TEXT,
  UNIQUE (source, upstream_id, payload_sha256));

CREATE TABLE documents (
  doc_id TEXT PRIMARY KEY, work_id TEXT REFERENCES works(work_id) ON DELETE SET NULL,
  kind TEXT NOT NULL CHECK (kind IN ('pdf','html','text')),
  origin_url TEXT, landing_url TEXT, source TEXT NOT NULL, license TEXT, oa_status TEXT,
  state TEXT NOT NULL CHECK (state IN ('cached','pinned','expiring','kept','archived','discarded')),
  cached_at TEXT NOT NULL, expires_at TEXT, review_batch_id TEXT, reask_count INTEGER NOT NULL DEFAULT 0,
  next_ask_at TEXT, pinned_at TEXT, archived_at TEXT, archive_path TEXT,
  archive_fallback INTEGER NOT NULL DEFAULT 0,
  archive_upload_state TEXT CHECK (archive_upload_state IN ('pending','uploaded','unknown')),
  discarded_at TEXT, trash_until TEXT, purged_at TEXT, decided_by TEXT, decided_channel TEXT,
  last_accessed_at TEXT, fetch_recipe_json TEXT NOT NULL, extract_status TEXT NOT NULL DEFAULT 'pending',
  CHECK (state <> 'archived' OR archive_path IS NOT NULL),
  CHECK (state <> 'discarded' OR discarded_at IS NOT NULL));
CREATE INDEX documents_state_expiry ON documents(state, expires_at);
CREATE INDEX documents_work ON documents(work_id);

CREATE TABLE files (
  file_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
  sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, media_type TEXT NOT NULL,
  storage_path TEXT, version_label TEXT, page_count INTEGER, final_url TEXT, http_status INTEGER,
  etag TEXT, last_modified TEXT, fetched_at TEXT NOT NULL, UNIQUE (doc_id, sha256));
CREATE INDEX files_sha ON files(sha256);

CREATE TABLE extractions (
  extraction_id TEXT PRIMARY KEY, file_id TEXT NOT NULL REFERENCES files(file_id) ON DELETE CASCADE,
  parser TEXT NOT NULL, parser_version TEXT NOT NULL, chunker_version TEXT NOT NULL,
  needs_ocr INTEGER NOT NULL DEFAULT 0, extracted_at TEXT NOT NULL);

CREATE TABLE chunks (
  chunk_id INTEGER PRIMARY KEY, extraction_id TEXT NOT NULL REFERENCES extractions(extraction_id) ON DELETE CASCADE,
  doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE, ord INTEGER NOT NULL,
  page_start INTEGER, page_end INTEGER, char_start INTEGER, char_end INTEGER, section TEXT,
  content TEXT NOT NULL, content_sha256 TEXT NOT NULL, UNIQUE (extraction_id, ord));

-- External-content FTS: rows are read back from chunks, so snippet() and highlight() work on any SQLite >= 3.37.
CREATE VIRTUAL TABLE chunks_fts USING fts5(content, section,
  content='chunks', content_rowid='chunk_id', tokenize='porter unicode61 remove_diacritics 2', prefix='2 3');
CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, content, section) VALUES (new.chunk_id, new.content, new.section); END;
CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, content, section) VALUES ('delete', old.chunk_id, old.content, old.section); END;
CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, content, section) VALUES ('delete', old.chunk_id, old.content, old.section);
  INSERT INTO chunks_fts(rowid, content, section) VALUES (new.chunk_id, new.content, new.section); END;
-- Chunks are written once per extraction; re-extraction inserts new rows. The update trigger exists for safety.

CREATE TABLE embeddings (
  content_sha256 TEXT NOT NULL, model TEXT NOT NULL, dim INTEGER NOT NULL, vector BLOB NOT NULL,
  created_at TEXT NOT NULL, PRIMARY KEY (content_sha256, model));

CREATE TABLE collections (name TEXT PRIMARY KEY, description TEXT, pin_members INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL);
CREATE TABLE collection_items (name TEXT NOT NULL REFERENCES collections(name) ON DELETE CASCADE,
  work_id TEXT NOT NULL REFERENCES works(work_id) ON DELETE CASCADE, note TEXT, added_at TEXT NOT NULL,
  PRIMARY KEY (name, work_id));

CREATE TABLE outbox (outbox_id INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, payload_json TEXT NOT NULL);
```

`cache.db` lives under `paths.data_dir` in Application Support and is backed up nightly (section 9.8). Only the stored files, the trash and the model cache are left out of backups.

### 8.2 Extraction and chunking

- **`extract_pdf`** runs in the worker with PyMuPDF. Page count is `len(doc)`. Text is taken per page with `sort=True`, the outline comes from `get_toc()`, and the references section is tagged `section="References"`.
- **`extract_html`** parses with `selectolax`. It drops nav, header, footer, script and style, keeps h1 to h3 as section markers, and outputs text with paragraph breaks.
- **`chunking.chunk(text_by_page, sections, target_tokens=400, overlap_tokens=50, hard_cap_chars=4000)`:**
  - Tokens are counted with a fast whitespace-and-punctuation tokenizer.
  - Text is split on paragraphs, then on sentences (a regex with an abbreviation guard), then at the hard cap.
  - A word is never split. Page numbers and character offsets are recorded for every chunk.
  - `CHUNKER_VERSION = "2.0"`.
- **Embeddings:**
  - The default model is `fastembed` `BAAI/bge-small-en-v1.5` (384 dimensions), cached in `paths.model_cache_dir`.
  - Chunks are encoded with `passage_embed` and queries with `query_embed`.
  - Vectors are stored as float32 little-endian BLOBs.
  - Search computes exact cosine similarity with NumPy over the cached vectors. `sqlite-vec` can replace this later behind the same function.

### 8.3 Local search

`search_cache` has three modes:

- **Keyword:** FTS5 with `bm25(chunks_fts, 1.0, 0.5)`, plus the v1 query sanitizer and its literal fallback (ported). A hit in the References section has its score multiplied by 0.5 in Python before ranking.
- **Semantic:** the top 50 chunks by cosine similarity.
- **Hybrid:** reciprocal rank fusion of the keyword and semantic results.

Snippets come from `snippet(chunks_fts, 0, '[', ']', ' ... ', 12)` for keyword hits. Semantic hits get the 300 characters around their best sentence.

Each result reports coverage: embedded chunks divided by all chunks, for the documents in scope.

## 9. Lifecycle, review and archive

### 9.1 State transitions

| From | Event | To | Side effects |
|---|---|---|---|
| (none) | fetch | cached | `expires_at = cached_at + 120 d` |
| cached | review run, `expires_at - now <= 3 d` | expiring | Assigned to today's batch |
| kept | review run, `next_ask_at <= now` | expiring | `reask_count += 1` |
| expiring | archive (owner in the UI, or agent through MCP) | archived | Archive job (9.3) |
| expiring | discard (owner in the UI, or agent through `cache_review_decide`) | discarded | Files to trash; `trash_until = now + 7 d`; MCP discards notify at once |
| cached, pinned or kept | owner discard on the UI Cache page (confirmed) | discarded | As above |
| expiring | keep | cached | `expires_at = now + 120 d` |
| expiring | pin, or membership in a pinning collection | pinned | `expires_at = NULL` |
| expiring | batch closes unanswered (`cache.batch_open_hours` after the notification) | kept | `next_ask_at = now + 7 d`; files stay |
| cached, pinned or kept | `library archive` | archived | Archive job; not destructive (the copy is verified before removal) |
| pinned | unpin | cached | `expires_at = now + 120 d` |
| discarded | undo before `trash_until` (UI Archive page, or `library restore`) | cached | Restore files from trash; `expires_at = now + 120 d` |
| discarded | `trash_until` passes | discarded | Purge job (below); `purged_at` set; the work, CSL and recipe are kept |

- `decided_by` is `owner` for the UI and `agent` for MCP. `decided_channel` is `ui` or `mcp`. Every transition writes an outbox row (3.5).
- **Trash purge.** At 10:00 each day, `trash_purge_notice` lists the items whose trash ends within 24 hours, in one notification with an undo link. `trash_purge` then removes items whose `trash_until` has passed: their file (subject to the file deletion rule in 3.4), their chunks and FTS rows, and any embeddings no other chunk uses.

### 9.2 Review batch

`LifecycleService.run_review(now)` runs at `cache.review_time_local`, or once on catch-up:

1. Select the candidates.
2. Create `review_batches(batch_id, created_at, notified_at, closes_at, item_count)`.
3. Send one notification through `NotifyService`, with `ui_path=/review/<batch_id>`.
4. Post the webhook message.

`cache_review_decide` checks that the `batch_id` is open and that every `doc_id` belongs to it.

### 9.3 Archive

`ArchiveService.archive(doc_id)`:

1. **Resolve the target.** Use `archive.confirmed_path` (required when `archive.target` is `auto`), then add `archive.subfolder` with `{year}` set to the archive year. Then check:
   - the folder exists;
   - it is writable, by writing and replacing the sentinel `.research-mcp-probe`;
   - there is free space greater than the file size plus 100 MB;
   - the `Google Drive` app process is running (`pgrep -x "Google Drive"`).
2. **Name the files.** The slug is `<first-author-family>-<year>-<title-key first 6 words>-<sha256[:6]>`. The files are `<slug>.<ext>` and `<slug>.meta.json`.
3. **Write in the target folder.** Write the hidden temporary file `.<slug>.<ext>.partial` there, then `fsync` it and rename it to `<slug>.<ext>`. Read the file back and compare its size and SHA-256. Write the sidecar the same way. Drive for desktop may upload a hidden partial file; the rename replaces it.
4. **On success:**
   - set `state=archived`, `archive_path`, `archived_at`, and `archive_upload_state='pending'`;
   - remove only the cached file (subject to the file deletion rule in 3.4). The extraction, chunks, FTS rows and embeddings **stay**, so the archived document remains searchable with `search_cache` and readable with `read` (ADR 0011). `files.storage_path` is cleared and `documents.archive_path` points to the Drive copy.
5. **If the target check fails:**
   - use `archive.fallback` and set `archive_fallback=1`;
   - raise an `archive_target_unavailable` health event.
   
   `ArchiveService.reconcile()` runs hourly when fallbacks exist. It moves the fallback files into the Drive target with the same verification.
6. **Upload confirmation.** Hourly, `reconcile()` reads `NSURLUbiquitousItemIsUploadedKey` for each pending archive. This uses pyobjc (extra `macos`); without the extra, the state is `unknown`.
   - When the key is true, the state becomes `uploaded`.
   - An item still `pending` 24 hours after archiving raises a notification.

**Sidecar fields:** `title`, `authors`, `csl`, `citation_apa`, `bibtex`, `source`, `identifiers`, `original_url`, `fetched_at`, `archived_at`, `sha256`, `size_bytes`, `archived_from` = `research-mcp 3.x`.

**macOS privacy (TCC).** Files in `~/Library/CloudStorage` are protected. The first archive write by the daemon's interpreter may need the owner's consent, and a background process may get no prompt at all.

- `doctor` runs `archive_access`, which writes and removes the sentinel, and reports `tcc_denied` with the fix: grant the daemon's interpreter Files and Folders access to Google Drive in System Settings, Privacy & Security.
- `research-mcp install` runs this write once in the foreground, so the prompt appears while the owner is present.

### 9.4 Disk and integrity

`DiskService.sample()` runs every 15 minutes and writes to `state.db.disk_samples`.

`MaintenanceService.daily()` runs these checks and records each one in `maintenance_runs`:

- `PRAGMA quick_check` on both databases;
- `INSERT INTO chunks_fts(chunks_fts) VALUES('integrity-check')`;
- missing-file and orphan scans.

Fix actions (`rebuild_fts`, `reembed_missing`, `clean_orphans` and `backup_state`) are job kinds. They can be started only from the UI or the CLI.

### 9.5 Collections

Collections do not pin by default (`pin_members` defaults to 0).

- A collection created with `pin_members=1` pins every document of its member works.
- Removing a work from the last pinning collection returns its documents to `cached`, with a fresh 120 days.

### 9.6 Legacy import

`LegacyImportService.run(path, mode, dry_run)` runs as the job kind `legacy_import`:

1. Open `<path>/arxiv_index.db` as `file:...?immutable=1`, so no WAL or SHM files are created.
2. Run the inventory and the pre-import queries from findings-functional section 6.3.
3. Map each row:
   - arXiv ids go through `normalize_arxiv`;
   - `doi:` and `doi/` go through `normalize_doi`;
   - `core:` and `core/` map to the `core` scheme;
   - `iam:<project>:<hash>` becomes an HTML document with `origin_url = pdf_path` and `source = docs_site_<project>`;
   - anything else maps to the `legacy` scheme, followed by a title lookup through `get_work`.
4. Group rows by normalized id and by file path. Keep the row with a non-empty title for metadata, and record both raw ids as `legacy` identifiers.
5. Copy each distinct file into the cache by SHA-256 and re-extract it with the v2 worker. If extraction fails, import the v1 chunks for that document with `parser="v1-import"`.
6. Set each document's state by mode:
   - `cache` (the default): `expires_at = now + 120 d`;
   - `archive`: archive each document;
   - `metadata_only`: create works and identifiers only.
7. Write `state_dir/imports/<timestamp>/report.json` and `report.md`.

### 9.7 Archive rebuild

`ArchiveService.reindex(root)` runs as the job kind `archive_reindex`, started from the UI Archive page or `research-mcp archive reindex [--dry-run]`:

1. Walk `archive.confirmed_path` plus `archive.subfolder` for every year folder (and the fallback folder), reading each `<slug>.meta.json` sidecar. Files without a sidecar are listed in the report and left alone.
2. For each sidecar, look the work up by its identifiers. Create the work, identifiers and an `archived` document (with `archive_path`) when missing; otherwise verify the stored `sha256` matches the file.
3. If the document has no extraction, chunks or embeddings for the current chunker and model, copy the PDF to `data_dir/tmp`, re-extract and embed it in the worker, then delete the temporary copy. The Drive file is opened read-only and never modified.
4. Write `state_dir/imports/<timestamp>/archive-reindex.json` and `.md` with counts: sidecars read, works created, documents verified, re-extracted, mismatched, files without sidecars.

### 9.8 Backups

`BackupService.backup_state()` runs nightly at 03:30. It uses the SQLite online backup API to copy `state.db` and `cache.db`, and it copies `config.toml`. The copies go to `state_dir/backups/<date>/`, and `backup.keep` days are kept. The stored files and the trash are not backed up.

## 10. Health, credentials and notifications

### 10.1 state.db schema (migration 0001)

```sql
CREATE TABLE calls (ts TEXT NOT NULL, source TEXT NOT NULL, op TEXT NOT NULL, status INTEGER,
  error_code TEXT, latency_ms INTEGER, bytes INTEGER, rl_remaining TEXT, rl_reset TEXT,
  cred_expires_at TEXT, correlation_id TEXT, attempt INTEGER NOT NULL DEFAULT 1);
CREATE INDEX calls_source_ts ON calls(source, ts);
CREATE TABLE call_rollups (hour TEXT NOT NULL, source TEXT NOT NULL, calls INTEGER, errors INTEGER,
  p50_ms INTEGER, p95_ms INTEGER, PRIMARY KEY (hour, source));
CREATE TABLE source_health (source TEXT PRIMARY KEY, state TEXT NOT NULL, reason TEXT, fix_hint TEXT,
  last_probe_at TEXT, last_probe_ok INTEGER, consecutive_failures INTEGER NOT NULL DEFAULT 0,
  rate_limited_until TEXT, budget_reset_at TEXT, quota_remaining TEXT, quota_reset TEXT,
  baseline_p95_ms INTEGER, calls_today INTEGER NOT NULL DEFAULT 0, api_version_seen TEXT,
  enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL);
CREATE TABLE credentials (name TEXT PRIMARY KEY, service TEXT NOT NULL, required_by TEXT NOT NULL,
  fingerprint TEXT, keychain_modified_at TEXT, expires_at TEXT, rotate_by TEXT,
  last_validated_at TEXT, last_result TEXT, state TEXT NOT NULL, last_used_at TEXT, updated_at TEXT NOT NULL);
CREATE TABLE searches (search_id TEXT PRIMARY KEY, ts TEXT NOT NULL, query_hash TEXT NOT NULL,
  query_len INTEGER NOT NULL, sources_json TEXT NOT NULL, statuses_json TEXT NOT NULL, latency_ms INTEGER);
CREATE TABLE jobs (job_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','running','succeeded','failed','cancelled')),
  params_json TEXT NOT NULL, progress REAL NOT NULL DEFAULT 0, cursor TEXT, result_json TEXT,
  error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE schedule_runs (job TEXT PRIMARY KEY, last_run_at TEXT, next_due_at TEXT NOT NULL);
CREATE TABLE notifications (notification_id TEXT PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL,
  severity TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL, ui_path TEXT,
  channels_json TEXT NOT NULL, acknowledged_at TEXT, snoozed_until TEXT, dedupe_key TEXT NOT NULL);
CREATE TABLE review_batches (batch_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, notified_at TEXT,
  closes_at TEXT NOT NULL, closed_at TEXT, item_count INTEGER NOT NULL);
CREATE TABLE review_events (ts TEXT NOT NULL, doc_id TEXT NOT NULL, batch_id TEXT, from_state TEXT NOT NULL,
  to_state TEXT NOT NULL, decided_by TEXT, channel TEXT);
CREATE TABLE disk_samples (ts TEXT PRIMARY KEY, cache_bytes INTEGER, files_bytes INTEGER, index_bytes INTEGER,
  embeddings_bytes INTEGER, trash_bytes INTEGER, free_cache_vol INTEGER, free_archive_vol INTEGER);
CREATE TABLE maintenance_runs (ts TEXT NOT NULL, check_name TEXT NOT NULL, ok INTEGER NOT NULL, detail TEXT);
```

Retention: `calls` 30 days; `call_rollups` 13 months; `disk_samples` 90 days; everything else is kept.

### 10.2 Probes and state evaluation

- `HealthService` schedules each source's probe at `spec.probe.cadence_s`, with 0 to 10% jitter. A probe is skipped when a successful call already happened in its window (FR-HLTH-04).
- `evaluate(source)` applies the table in PRD-health section 2.2, most severe state first. Its inputs are:
  - the last 20 calls from `calls`;
  - `consecutive_failures`;
  - the 7-day p95 baseline from the rollups;
  - `rate_limited_until` and `budget_reset_at`;
  - the `credentials` table;
  - `spec.shutdown_on`.
- On a state change, the service writes `source_health` and emits `HealthEvent(kind, subject, severity, ui_path, dedupe_key)` to `NotifyService`.

### 10.3 Credential validation

| Validation | Method |
|---|---|
| `github_rate_limit` | `GET https://api.github.com/rate_limit`, which is free. A 401 means `invalid`. `resources.*.remaining` gives the quota, and the response header `github-authentication-token-expiration` gives the expiry. |
| `header_expiry` | The expiry header is parsed on every authenticated call (GitHub). |
| `probe` | The source probe, with credentials attached. Auth failures are classified as `invalid`. |
| Google API key | A probe to `https://developerknowledge.googleapis.com/v1/documents:searchDocumentChunks?query=documentation&pageSize=1` with the key in `x-goog-api-key`. `API_KEY_INVALID` and `SERVICE_DISABLED` map to `invalid`. The same key also serves `google_pse`, whose own probe is metered (5.5). |
| `google_adc` (Google sign-in, M1) | `GoogleAdcProvider` refreshes the token (free), then the Vertex probe reads the engine metadata (free). `missing`: no sign-in found. `invalid`: refresh refused, `SERVICE_DISABLED`, or `PERMISSION_DENIED` on the engine (the reason is kept). Fix text: `gcloud auth application-default login`, plus the engine's console page for permission problems. Token expiry is about an hour and renews itself, so it never raises `expiring_soon`. |
| `serpapi_account` | `GET https://serpapi.com/account.json` (free). 401 means `invalid`; the searches-left figure sets `quota_low`. |
| Brave | Passive: rate-limit headers on each call set quota; 401 or 403 on a call means `invalid`. |
| Missing or locked | `SecretProvider.get` returns `missing` or `keychain_locked`. If the Keychain is locked, every credential shows `keychain_locked`, and only one notification fires ("Keychain locked"); there is no per-key notice. |
| No expiry exposed | `rotate_by = keychain_modified_at + 180 d`, unless set by the owner. |

### 10.4 Notifications

- **`NotifyService.emit(event)`** dedupes by `dedupe_key` for the life of the state, applies quiet hours, delivers to the channels, and stores the notification in `notifications`.
- **macOS:** `terminal-notifier -title "Research MCP" -subtitle <subject> -message <body> -group research-mcp-<dedupe_key> -execute "<venv>/bin/research-mcp ui --path <ui_path>"`.
  - The `ui` command mints its one-time login token when the notification is clicked, so no token sits in the notification itself, in a process argument list or in Notification Center.
  - The fallback is `osascript -e 'display notification ...'`, which cannot be clicked through.
  - `doctor` reports whether `terminal-notifier` is installed.
- **Webhook:** `POST notify.webhook_url` with JSON `{type, severity, subject, body, ui_path, ts}` and `Authorization: Bearer <NOTIFY_WEBHOOK_TOKEN>` when that item exists. The timeout is 5 s, there are at most 2 retries, and failures are logged.
- **Digest:** at 08:00 local time, one notification summarizes the unresolved items.

### 10.5 Doctor and endpoints

`research-mcp doctor` runs these checks, each with a code and fix text:

| Check | What it verifies |
|---|---|
| `daemon_alive` | `GET /healthz` answers. |
| `keychain_readable` | The Keychain can be read, and is not locked. |
| `contact_email` | A contact email is set. |
| one check per credential | The credential's current state. |
| one probe per enabled source | The source responds; with `--quick`, only free probes run. |
| `archive_target` and `archive_access` | The archive folder is available; TCC access is granted. |
| `disk` | Disk thresholds. |
| `schema_versions` | Database schema versions match the code. |
| `review_overdue` | No review missed by more than 24 hours. |
| `backup_recent` | A backup ran in the last 48 hours. |
| `terminal_notifier` | terminal-notifier is installed. |
| `launchd_jobs` | `launchctl print gui/$UID/local.research-mcpd` and the other two jobs. |

- **Flags:**
  - `--liveness` checks only `daemon_alive` and `keychain_readable`.
  - `--notify` sends one summary notification when anything is not ok, and only when the result changed since the last notify.
- **Exit code:** 0 when no check is critical.

The daemon also serves three endpoints:

| Endpoint | Auth | Returns |
|---|---|---|
| `/healthz` | none | `{"status":"ok","version":"3.x.y"}` |
| `/readyz` | none | Ok when the stores are open, the scheduler is running and the Keychain is readable; 503 otherwise |
| `/api/status` | bearer token or a UI session | JSON of sources, credential metadata, quotas, jobs, cache stats, disk, the archive target and the last 20 notifications |

## 11. UI

- The UI is mounted at `/ui` in the daemon's Starlette app. Templates live in `ui/templates`, one per page in PRD-ui section 2.2, plus a base layout with navigation and a banner slot.
- **Auth:**
  - `research-mcp ui [--path P]` creates a one-time token (32 random bytes, valid for 5 minutes) through `POST /api/ui-token`, using the daemon bearer token, and opens `http://127.0.0.1:<port>/ui/login?t=...&next=P` in the browser.
  - `GET /ui/login` consumes the token, sets the session cookie `rmcp_session` (HttpOnly, SameSite=Strict, `Path=/`, 12-hour life), and redirects to `next`.
  - Uvicorn access logging is off, so tokens never reach a log.
  - Every POST requires the header `X-CSRF-Token`, which htmx sends from a meta tag.
  - The Host must be `127.0.0.1:<port>` or `localhost:<port>`. If an Origin header is present, it must match.
- **Partial refresh:** page fragments reload with `hx-get` every 10 s. Confirmations use `hx-confirm` with a summary rendered by the server.
- **Routes:**
  - Pages: `/ui/` (source board), `/ui/sources/<id>`, `/ui/credentials`, `/ui/quota`, `/ui/jobs`, `/ui/cache`, `/ui/review/<batch_id>`, `/ui/archive`, `/ui/maintenance`, `/ui/events`, `/ui/settings`.
  - Actions: POST routes under the same paths, at `/action/<name>`.

## 12. Packaging, CI, deployment and work breakdown

### 12.1 Packaging and CI

- **Dependencies** in `pyproject.toml`: `mcp>=1.27,<2`, `httpx[http2]`, `anyio`, `pydantic>=2`, `pydantic-settings`, `aiosqlite`, `uvicorn`, `starlette`, `jinja2`, `selectolax`, `defusedxml`, `python-ulid`, `psutil`, `tomli-w`.
- **Extras:** `pdf = ["pymupdf"]`, `embeddings = ["fastembed", "numpy"]` and `macos = ["pyobjc-framework-Cocoa"]`; from M1, `gcp = ["google-auth"]` (with `google.*` added to the mypy `ignore_missing_imports` overrides).
- **Dev group:** `pytest`, `pytest-asyncio`, `pytest-cov`, `respx`, `hypothesis`, `ruff` and `mypy`.
- **`[tool.pytest.ini_options]`:** `addopts = "--import-mode=importlib -m 'not live'"`, `asyncio_mode = "auto"` and `markers = ["live: real upstream calls"]`.
- **`[tool.ruff]`:** `line-length = 100`, `target-version = "py312"`, `extend-exclude = ["tools/gen_test_plan.py", "tools/gen_m0_plan.py"]` (design-time generators, kept outside the code rules); `[tool.ruff.lint] select = ["E","F","I","W","B","UP","SIM","ASYNC","BLE","S","C90"]`; `[tool.ruff.lint.per-file-ignores] "tests/**" = ["S101","S105","S106","S108"]`; `[tool.ruff.lint.mccabe] max-complexity = 12`.
- **`[tool.mypy]`:** `strict = true`, `python_version = "3.12"`, `files = ["src"]`; `[[tool.mypy.overrides]] module = ["fitz.*","fastembed.*","objc.*","Foundation.*","selectolax.*"] ignore_missing_imports = true`.
- **Dev stubs:** `types-defusedxml`, `types-psutil`.
- **Package data:** `research_mcp/platform/migrations/**/*.sql`, `research_mcp/ui/templates/*.html`, `research_mcp/ui/static/*` `research_mcp/packaging/launchd/*.plist.template` and, from M1, `research_mcp/packaging/defaults.toml`.
- **Scripts:** `research-mcp = research_mcp.cli:main` and `research-mcpd = research_mcp.daemon:main`.

`tools/ci.sh` must start with `#!/usr/bin/env bash` and be executable; the ECC gate runs commands without a shell. It has two modes.

**`tools/ci.sh --python-only`** runs on every work unit:

1. `uv run ruff check`
2. `uv run ruff format --check`
3. `uv run mypy src`
4. `uv run pytest -q --cov=research_mcp --cov-report=term` (coverage is reported, not gated)
5. Each generator check, run only when its script exists:
   - `uv run python tools/gen_test_plan.py --check`
   - `uv run python tools/gen_m0_plan.py --check`
   - `uv run python tools/gen_inventory.py --check`

**`tools/ci.sh`** with no flag runs at milestone exit and in GitHub Actions. It adds:

- `--cov-fail-under=85`;
- `uv build`;
- `uv run research-mcp --help`, once `research_mcp/cli.py` exists.

**CLI subcommands** (`cli.py`):

| Command | Purpose |
|---|---|
| `serve` | Run the daemon in the foreground. |
| `stdio` | The stdio shim for MCP clients. |
| `doctor [--json] [--notify] [--quick] [--liveness]` | Run health checks (10.5). |
| `ui [--path P]` | Open the UI with a one-time login. |
| `sources [--markdown] [check --live [--id] [--refresh-fixtures]]` | Source inventory and live checks. |
| `config get\|set <key> [value]` | Read or change config. |
| `install [--print-client-config]` | Install the launchd jobs and print client config. |
| `upgrade` | Upgrade with rollback (12.2). |
| `secrets list\|import [--dry-run]\|scrub-client-configs\|rotate-token` | Manage Keychain items. |
| `import-legacy <path> [--dry-run] [--mode]` | Import the v1 corpus (9.6). |
| `archive reindex [--dry-run]` | Rebuild the searchable archive from the Drive folder (9.7). |

`secrets list` prints names, fingerprints and states only.

### 12.2 launchd, install and upgrade

**Templates** in `src/research_mcp/packaging/launchd/` (package data):

| Template | Runs | Schedule and options |
|---|---|---|
| `local.research-mcpd.plist.template` | `__VENV__/bin/research-mcpd` | `RunAtLoad` true, `KeepAlive` true, `ThrottleInterval` 30, `ProcessType` Background, `StandardErrorPath` `__LOGS__/daemon.err.log` |
| `local.research-mcp-doctor.plist.template` | `research-mcp doctor --notify` | `StartCalendarInterval` Hour 8 Minute 52 |
| `local.research-mcp-watchdog.plist.template` | `research-mcp doctor --liveness --notify` | `StartInterval` 900 |

**`research-mcp install`:**

1. Fills the placeholders.
2. Creates the folders.
3. Generates `DAEMON_TOKEN` through `SecretProvider.set` if it is absent.
4. Runs the foreground `archive_access` write (9.3); this step is added in M2 with the archive service.
5. Loads the three jobs with `launchctl bootstrap gui/$UID`.
6. Prints the client configs.

**`research-mcp upgrade`:**

1. Records the current lock file and the `uv tool` environment path.
2. Stops the daemon.
3. Backs up `state.db` and `cache.db` (online backup API) to `state_dir/backups/pre-upgrade-<timestamp>/`.
4. Runs `uv tool upgrade research-mcp` (or `uv sync` for a source checkout).
5. Runs the migrations, then `doctor --quick`, then restarts the daemon.
6. If doctor reports a critical check, reinstalls the recorded version (`uv tool install research-mcp==<old>`), restores both databases from step 3, and restarts the daemon.

Migrations are forward-only; the step 3 backup is what makes rollback possible.

### 12.3 Work breakdown, milestone M0 (ECC pilot)

Each unit is one ECC work unit: one branch, its listed files, and its acceptance tests (TEST-PLAN Appendix A). Each unit's acceptance commands are its own test files plus `tools/ci.sh --python-only`. The unit is reviewed by the other model family.

| Unit | Title | Implements | Files (scope) | Depends on | Risk |
|---|---|---|---|---|---|
| M0-01 | Repository scaffold, packages and CI script | 1, 12.1 | `pyproject.toml`, `uv.lock`, `.python-version`, `src/research_mcp/__init__.py`, `src/research_mcp/version.py`, `src/research_mcp/core/__init__.py`, `src/research_mcp/platform/__init__.py`, `src/research_mcp/sources/__init__.py`, `src/research_mcp/services/__init__.py`, `src/research_mcp/mcp_app/__init__.py`, `src/research_mcp/ui/__init__.py`, `src/research_mcp/testing/__init__.py`, `tools/ci.sh`, `.github/workflows/ci.yml`, `tests/conftest.py`, `tests/unit/test_version.py`, `tests/unit/test_import_side_effects.py`, `tests/unit/test_network_guard.py`, `src/research_mcp/packaging/__init__.py` | none | high |
| M0-02 | Identifier normalization | 6 (`core/ids.py`) | `core/ids.py`, `tests/unit/core/test_ids.py` | M0-01 | medium |
| M0-03 | Specs, models, errors, envelope, budget and test clock | 3.7 (types, `HttpError`, context), 4 (`core/specs.py`, `core/models.py`) | `core/specs.py`, `core/models.py`, `core/errors.py`, `core/context.py`, `core/envelope.py`, `core/budget.py`, `core/timeutil.py`, `testing/clock.py`, `tests/unit/core/test_envelope.py`, `tests/unit/core/test_budget.py`, `tests/unit/core/test_models.py` | M0-02 | medium |
| M0-04 | Settings and paths | 2 | `settings.py`, `tests/unit/test_settings.py` | M0-01 | medium |
| M0-05 | Secrets and Keychain provider | 3.1 | `platform/secrets.py`, `tests/unit/platform/test_secrets.py` | M0-04 | high |
| M0-06 | Redaction and structured logging | 3.2 | `platform/redact.py`, `platform/logging.py`, `tests/unit/platform/test_redact.py`, `tests/unit/platform/test_logging.py`, `tests/security/test_no_secret_in_logs.py` | M0-05 | high |
| M0-07 | Async HTTP client, rate limits and downloader | 3.3, 3.4 | `platform/http.py`, `platform/download.py`, `platform/ratelimit.py`, `tests/unit/platform/test_http.py`, `tests/unit/platform/test_ratelimit.py`, `tests/unit/platform/test_downloader.py`, `tests/security/test_scoped_credentials.py` | M0-03, M0-06 | high |
| M0-08 | Stores and migrations | 3.5, 8.1, 10.1 | `platform/stores.py`, `platform/migrations/state/0001_init.sql`, `platform/migrations/cache/0001_init.sql`, `tests/unit/platform/test_stores.py` | M0-03 | high |
| M0-09 | Source contract, registry and conformance suite | 4 (`sources/base.py`), 5.1, 5.2 | `sources/base.py`, `sources/registry.py`, `testing/adapters.py`, `tests/sources/conftest.py`, `tests/sources/test_conformance.py`, `tests/unit/sources/test_registry.py`, `tests/unit/sources/test_adapter_imports.py` | M0-02, M0-07 | high |
| M0-10 | arXiv adapter | 4, 5.2 | `sources/arxiv.py`, `tests/sources/arxiv/fixtures/*`, `tests/sources/arxiv/test_arxiv.py` | M0-09 | medium |
| M0-11 | Crossref adapter | 4, 5.2 | `sources/crossref.py`, `tests/sources/crossref/fixtures/*`, `tests/sources/crossref/test_crossref.py` | M0-09 | medium |
| M0-12 | OpenAlex adapter | 4, 5.2 | `sources/openalex.py`, `tests/sources/openalex/fixtures/*`, `tests/sources/openalex/test_openalex.py` | M0-09 | medium |
| M0-13 | Grouping, merge and federation service | 6 (`services/works.py`), 7.1 | `services/federation.py`, `services/works.py`, `tests/services/test_federation.py`, `tests/services/test_works.py` | M0-09 | high |
| M0-14 | MCP app: M0 tools, the sources resource and `@tool_boundary` | 3.7 (`tool_boundary`), 7.2 (M0 rows), 7.3 (M0 row), 7.4 (`build_mcp`) | `mcp_app/server.py`, `mcp_app/tools_discovery.py`, `mcp_app/resources.py`, `tests/contract/conftest.py`, `tests/contract/test_tools_discovery.py`, `tests/contract/test_tool_contract.py` | M0-08, M0-13 | high |
| M0-15 | Daemon, composition root, scheduler and stdio shim | 3.6 (jobs, scheduler), 7.4 (mount), 10.5 (healthz, readyz) | `app.py`, `daemon.py`, `shim.py`, `platform/auth.py`, `platform/jobs.py`, `platform/scheduler.py`, `testing/launchctl.py`, `tests/unit/test_app.py`, `tests/unit/test_shim.py`, `tests/unit/test_jobs.py`, `tests/unit/test_scheduler.py`, `tests/security/test_loopback_auth.py` | M0-05, M0-14 | high |
| M0-16 | CLI, install, doctor skeleton and launchd templates | 10.5 (doctor skeleton), 12.1 (CLI), 12.2 | `cli.py`, `packaging/launchd/local.research-mcpd.plist.template`, `packaging/launchd/local.research-mcp-doctor.plist.template`, `packaging/launchd/local.research-mcp-watchdog.plist.template` (all under src/research_mcp), `tools/gen_inventory.py`, `docs/generated/sources.md`, `tests/unit/test_cli.py`, `tests/unit/test_install.py` | M0-15 | medium |

Notes on the M0 plan:

- **Package scaffolding.** M0-01 declares every dependency, extra and pytest setting in 12.1, and creates every package `__init__.py`. No later unit edits `pyproject.toml`, `uv.lock` or an `__init__.py`.
- **No test packages.** Test folders have no `__init__.py`; pytest runs in importlib mode.
- **Parallel units.** Scopes do not overlap, so units in the same wave can run in parallel.
- **Source discovery.** The registry finds adapters, so adapter units touch no shared file.
- **Fixtures.** In the scope column, `fixtures/*` stands for the seven fixtures in 5.2. The generated plan lists them by name.

Waves:

1. M0-01
2. M0-02, M0-04
3. M0-03, M0-05
4. M0-06, M0-08
5. M0-07
6. M0-09
7. M0-10, M0-11, M0-12, M0-13
8. M0-14
9. M0-15
10. M0-16

### 12.4 Later milestones (unit lists written when the milestone starts)

| Milestone | Planned units (outline) |
|---|---|
| M1 | One unit per adapter or small group: 39 adapter modules (42 sources) in about 24 units, including the `reference` group (Library of Congress, Open Library, Wikipedia), including the `web` group (the four web adapters and `sitequery.py`), `GoogleAdcProvider`, `defaults.toml` with the v1 site set and docs-site instances, the `site_set` argument and the web fallback in federation. Adapter units do not touch `docs/generated/sources.md`; one closing unit regenerates the inventory. Also: `McpUpstreamPort` and `UpstreamMcpAdapter`; the citations, authors, cite and integrity services and tools; the health, credential and notify services; `ops_status` and `research://status`; prompts; the full set of doctor checks. |
| M2 | `WorkerRunner`; PDF and HTML extraction; chunking; embeddings; the cache service with `fetch`, `read` and `search_cache` (including archived documents); the lifecycle and review tools and the trash purge; the archive service, reconcile, upload confirmation and the archive rebuild job; collections; crawl jobs; disk, maintenance and backup. |
| M3 | UI auth and layout; one unit per page group: the board and source detail; credentials and quota; jobs and events; cache, review and archive; maintenance and settings. |
| M4 | `secrets import` and `scrub-client-configs`; legacy import; the client config printer; the tool map; the cutover checklist. |

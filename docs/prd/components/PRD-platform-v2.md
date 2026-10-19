# Component PRD: Platform and Security (v2)

- **Parent:** [PRD v3](../PRD-v3.md), goals G3 and G7; NFR-01 to NFR-10; supersedes [v1](PRD-platform-v1.md)
- **Design:** [HLD v3](../../design/HLD-v3.md) sections 3 and 9; [LLD v3](../../design/LLD-v3.md) sections 2, 3 and 12; [ADR 0012](../../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md); ADRs [0002](../../adr/0002-one-daemon-with-stdio-shims.md) to [0005](../../adr/0005-async-io-cpu-off-loop.md), [0009](../../adr/0009-no-sql-untrusted-content.md)
- **Review findings addressed:** ARCH-01 to ARCH-03, ARCH-06 to ARCH-09, ARCH-13 to ARCH-15, ARCH-17 to ARCH-21, OPS-01 to OPS-14, OPS-19 to OPS-22

## Changes from v1

For the optional web-search sources (ADR 0012): FR-PLAT-10 records the one credential v2 does not keep in the Keychain (the owner's Google sign-in, owned by `gcloud`); FR-PLAT-12 names SerpAPI as the case where a key may travel as a query parameter; FR-PLAT-51 adds the `gcp` extra. The M0 scope is unchanged: the `gcp` extra is added in M1 with the Vertex source.

## 1. Purpose

Everything the sources, search, cache, health and UI components stand on: the process model, configuration and secrets, the HTTP client, the error and result shape, logging, packaging, CI and upgrades.

## 2. Requirements

### 2.1 Process and transport

| ID | Requirement | Priority |
|---|---|---|
| FR-PLAT-01 | One daemon, `research-mcpd`, runs under a launchd LaunchAgent (`RunAtLoad`, `KeepAlive`) and owns all HTTP clients, rate limiters, stores, the scheduler, the MCP endpoint and the UI. | Must |
| FR-PLAT-02 | `research-mcp stdio` is the command every MCP client launches (clients never hold the daemon token). It relays stdio to the daemon's loopback endpoint with the bearer token; if the daemon is down it asks launchd to start it and retries; if that fails it returns one clear MCP error. | Must |
| FR-PLAT-03 | The daemon serves MCP over streamable HTTP on `127.0.0.1` only, requires a bearer token (from the Keychain, compared in constant time), checks Host and Origin, and refuses to start on a non-loopback address. | Must |
| FR-PLAT-04 | The app is built by one composition root (`build_app(settings)`) with a lifespan that opens and closes every port. Importing any module does no I/O, reads no environment and configures no logging. | Must |
| FR-PLAT-05 | No tool blocks the event loop: network I/O is async; PDF parsing, extraction and embedding run in one subprocess per task; SQLite work runs off-loop. | Must |
| FR-PLAT-06 | Long operations run as jobs (persisted, with progress, cancellation and resume) and return a job id. | Must |

### 2.2 Configuration and secrets

| ID | Requirement | Priority |
|---|---|---|
| FR-PLAT-08 | One settings model, loaded from `~/.config/research-mcp/config.toml` plus `RESEARCH_MCP_*` environment overrides, validated at startup with clear errors; per-source sections come from each `SourceSpec`. | Must |
| FR-PLAT-09 | Paths follow macOS conventions: config in `~/.config/research-mcp/`; state and cache data in `~/Library/Application Support/research-mcp/` (cache data must not live in `~/Library/Caches`, which can be purged); only re-downloadable model files in `~/Library/Caches/research-mcp/`; logs in `~/Library/Logs/research-mcp/`. | Must |
| FR-PLAT-10 | Secrets are Keychain generic passwords with service `research-mcp/<NAME>` and account set to the macOS user. Configuration holds only references (`keychain:research-mcp/<NAME>`). No secret is written to any file, and no secret value is ever passed in a process argument list (Keychain writes go through stdin). The one exception is the owner's Google sign-in for Vertex AI Search: `gcloud` owns its file; v2's own code never opens or copies that file (the `google-auth` library reads it) and holds only a short-lived access token in memory. | Must |
| FR-PLAT-11 | Secret values are wrapped in a `Secret` type whose text form is `Secret(name=..., fp=...)`; only the platform HTTP, MCP-client and auth modules reveal the value. | Must |
| FR-PLAT-12 | Credentials are attached only to requests whose origin matches the credential's source, in a header where the API allows it (for example `x-goog-api-key`). Where the API accepts only a query parameter (SerpAPI), the URL is never logged and the redactor masks the parameter. | Must |
| FR-PLAT-13 | One redaction filter, attached to every log handler so third-party and child-logger records are covered, masks known secret values and credential-like patterns (`key=`, `api_key=`, `token=`, `Authorization`, `X-Subscription-Token`, `x-goog-api-key`, `AIza`, `ghp_`, `github_pat_` prefixes) in every log record, error message, tool result, UI page and notification. | Must |
| FR-PLAT-14 | Tool errors never include raw exception text or upstream error bodies; they return `{code, message, retryable, correlation_id}`, and the details go to the redacted log. | Must |
| FR-PLAT-15 | Secrets are read once at start and kept in memory; "Reload credentials" and `SIGHUP` re-read them. | Must |
| FR-PLAT-16 | The HTTP bearer token for the daemon is generated at install, stored in the Keychain, and can be rotated from the UI. | Must |

### 2.3 Local access and untrusted content

| ID | Requirement | Priority |
|---|---|---|
| FR-PLAT-20 | There is no free-form SQL tool (open decision O4). | Must |
| FR-PLAT-21 | No tool reads a local file outside the cache root, and no tool accepts a caller-chosen local path. | Must |
| FR-PLAT-22 | If DuckDB is used internally, its connection has external access off, allowed directories limited to the cache, extension auto-install and auto-load off, and configuration locked. | Must |
| FR-PLAT-25 | Text fetched from the internet (PDF text, web pages, READMEs, abstracts, snippets) is returned inside an envelope marked `untrusted` with its source; the server instructions tell clients to treat it as data. | Must |
| FR-PLAT-26 | Every tool declares MCP annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). | Must |
| FR-PLAT-27 | State-changing tools (`fetch`, `library` actions, collection changes, review decisions) are clearly described as such; no tool hard-deletes. | Must |

### 2.4 Results, errors and HTTP

| ID | Requirement | Priority |
|---|---|---|
| FR-PLAT-30 | Every tool returns one envelope, `{data, source_status, warnings, next_cursor, truncated}`, as a typed model so the MCP SDK emits an output schema and structured content. Outputs fit the response budget (default 64 KB) and page with cursors beyond it. | Must |
| FR-PLAT-31 | Every numeric argument has bounds in its signature; every enumerated argument is a closed set. | Must |
| FR-PLAT-32 | One error taxonomy (`ErrorCode`) distinguishes at least: `invalid_argument`, `not_found`, `unconfigured`, `auth_failed`, `rate_limited`, `upstream_error`, `upstream_timeout`, `budget_exhausted`, `too_large`, `blocked_by_policy`, `internal`. | Must |
| FR-PLAT-33 | One shared async HTTP client sets timeouts, restricts each source to its declared hosts, retries 429, 500, 502, 503, 504 and connection errors with jitter and honors `Retry-After`, applies per-source token buckets and concurrency limits that are global across all clients, caps bytes while streaming, sends one user agent with the owner contact, and records telemetry for every call. | Must |

### 2.5 Logging

| ID | Requirement | Priority |
|---|---|---|
| FR-PLAT-40 | Logs are JSON lines in `~/Library/Logs/research-mcp/research-mcp.jsonl`, rotated at 10 MB with 5 files kept. stderr receives warnings and errors only. | Must |
| FR-PLAT-41 | Log fields: time, level, event, correlation id, tool, source, operation, status, error code, latency, bytes, job id, attempt. | Must |
| FR-PLAT-42 | Query text is logged as a hash and length unless debug logging is on. | Should |

### 2.6 Packaging, CI and upgrades

| ID | Requirement | Priority |
|---|---|---|
| FR-PLAT-50 | `src/` layout, package `research_mcp`, Python 3.12, managed with `uv` and a committed lock file. Console scripts: `research-mcp` (CLI: `serve`, `stdio`, `doctor`, `ui`, `sources`, `config`, `install`, `upgrade`, `secrets`, `import-legacy`) and `research-mcpd`. | Must |
| FR-PLAT-51 | Heavy dependencies are extras: `pdf` (PyMuPDF), `embeddings` (fastembed, NumPy), `macos` (pyobjc, for Drive upload checks), `gcp` (google-auth, for Vertex AI Search). A search-only install needs none of them. | Must |
| FR-PLAT-52 | `tools/ci.sh --python-only` (run on every work unit) runs ruff (rules E, F, I, W, B, UP, SIM, ASYNC, BLE, S, C90), ruff format check, mypy in strict mode on `src/`, pytest with coverage reported, and the generator checks; full `tools/ci.sh` (milestone exit and CI) adds the 85% coverage gate, a wheel build and the `--help` smoke test. | Must |
| FR-PLAT-53 | GitHub Actions runs `tools/ci.sh` on macOS and Linux, Python 3.12 and 3.13, with SHA-pinned actions, `permissions: contents: read`, a secret scan, and a weekly dependency audit. | Should |
| FR-PLAT-54 | `research-mcp install` writes the launchd plists from templates, creates the folders, generates the daemon token, and prints the client configuration snippets (no secrets in them). | Must |
| FR-PLAT-55 | `research-mcp upgrade` stops the daemon, syncs dependencies, runs migrations, runs `doctor`, and restarts; on a failed `doctor` it rolls back to the previous environment. | Should |
| FR-PLAT-56 | Database schemas are versioned with `PRAGMA user_version` and numbered migrations run in a transaction at start; the daemon refuses to start on a database newer than the code. | Must |
| FR-PLAT-57 | `state.db`, `cache.db` and `config.toml` are backed up nightly (7 kept), optionally copied to `Research Archive/_state/` in Drive. Stored files and the trash are not backed up (archived items live in Drive). | Should |
| FR-PLAT-58 | The project version starts at 3.0.0 so it never collides with v1's 2.0.0 package metadata. | Must |

## 3. Acceptance

Tests `AT-PLAT-*` and the security suite `AT-SEC-*` in [TEST-PLAN v3](../../test-plan/TEST-PLAN-v3.md).

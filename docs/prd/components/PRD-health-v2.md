# Component PRD: Health, Credentials and Notifications (v2)

- **Parent:** [PRD v3](../PRD-v3.md), goals G4 and G5; supersedes [v1](PRD-health-v1.md)
- **Design:** [HLD v3](../../design/HLD-v3.md) section 7; [LLD v3](../../design/LLD-v3.md) section 10; [ADR 0012](../../adr/0012-domain-neutral-scope-keep-v1-endpoints-web-search-sources.md)
- **Review findings addressed:** OPS-11, OPS-14, OPS-15, OPS-16, OPS-23, OPS-24, FUNC-13

## Changes from v1

The optional web-search sources (ADR 0012) add one credential kind, the owner's Google sign-in for Vertex AI Search (FR-HLTH-25), and daily caps that reuse the `budget_exhausted` state. FR-HLTH-21 lists the new validation methods.

## 1. Purpose

Breadth only helps if the owner knows which sources work. This component watches every source and every credential, tells the owner when something changes, and says exactly how to fix it.

## 2. Requirements

### 2.1 Telemetry and probes

| ID | Requirement | Priority |
|---|---|---|
| FR-HLTH-01 | Every outbound call records: time, source, operation, HTTP status, classified error code, latency, bytes, parsed rate-limit headers, parsed credential-expiry header and a correlation id. Raw rows are kept 30 days; hourly rollups 13 months. | Must |
| FR-HLTH-02 | Every source has a cheap probe declared in its spec, with a cost class and cadence (default hourly for free sources, 6 to 24 hours for metered ones). Probes go through the same rate limiter as real traffic. | Must |
| FR-HLTH-03 | A probe checks the response shape, not only the status code, so an endpoint that returns 200 with a changed format is detected. | Must |
| FR-HLTH-04 | A probe is skipped when a real call in the same window already showed the source working (passive evidence first). | Should |
| FR-HLTH-05 | Local targets are probed too: cache database, embeddings, archive folder and disk. | Must |

### 2.2 Source states

The worst applicable state wins.

| State | Rule |
|---|---|
| `disabled` | Turned off in configuration or the UI. |
| `unconfigured` | A required credential or extra is missing. Shown neutral, not red. |
| `down` | 3 failed probes in a row; or all of at least 5 calls in 15 minutes failed; or a probe failed its shape check. |
| `credential_invalid` | A required credential is invalid. |
| `budget_exhausted(reset)` | A metered source reported its daily or period budget spent (for example OpenAlex), or the owner's budget cap was reached; skipped until the reset time. |
| `rate_limited(until)` | The source returned 429 with a retry time beyond 60 seconds; skipped until then. |
| `degraded` | Error rate above 10% over the last 20 calls; or p95 latency above 3 times its 7-day baseline; or recent short 429s; or quota low. |
| `credential_expiring(days)` | A credential expires within 14 days. |
| `deprecated(days)` | The provider has announced a shutdown date. |
| `ok` | None of the above. |

| ID | Requirement | Priority |
|---|---|---|
| FR-HLTH-10 | Source states follow the table above and are recomputed after every probe and every call batch. | Must |
| FR-HLTH-11 | Each source exposes: state, reason, fix hint, last probe time and result, calls in 24 hours, error rate, p50 and p95 latency, last classified error, quota remaining and reset, and credential badges. | Must |
| FR-HLTH-12 | Federated search reads source states to skip `down`, `rate_limited` and `budget_exhausted` sources (FR-SRCH-08). | Must |

### 2.3 Credential states

| State | Rule |
|---|---|
| `ok` | Validated within its cadence; no expiry, or expiry more than 14 days away. |
| `expiring_soon(days)` | Expiry within 14 days (warning) or 3 days or fewer (critical). Expiry comes from the provider (for example GitHub's `GitHub-Authentication-Token-Expiration` header, a service-account key's `validBeforeTime`) or from a `rotate_by` date the owner sets. |
| `invalid` | Last validation or call failed authentication (401; 403 with an auth reason; Google `API_KEY_INVALID`; OAuth `invalid_grant`). |
| `missing` | Referenced in configuration but not found in the Keychain. |
| `keychain_locked` | The Keychain could not be read (locked or user interaction not allowed). Applies to every credential at once and produces one notification, not one per key. |
| `quota_low(pct)` | Less than 10% of the period allowance remains. |
| `unknown_expiry` | Valid, but the provider does not expose an expiry; shows key age and `rotate_by`. |

| ID | Requirement | Priority |
|---|---|---|
| FR-HLTH-20 | Credential metadata is stored, never values: name, Keychain service, fingerprint (first 8 hex characters of the SHA-256 of the value, to notice rotation), Keychain modification date, `expires_at`, `rotate_by`, last validated time, last result and state. | Must |
| FR-HLTH-21 | Each credential has a validation method declared by its source: a passive header (GitHub expiry, Brave rate-limit headers), a free account or rate-limit endpoint (GitHub `/rate_limit`, the SerpAPI account endpoint), a Google sign-in token refresh (FR-HLTH-25), or a minimal probe call. Validation of a metered source never spends a billed query when a free method exists. | Must |
| FR-HLTH-22 | Keys that never expire get a default `rotate_by` of 180 days from their Keychain modification date, which the owner can change or clear. | Should |
| FR-HLTH-23 | After the owner rotates a key in the Keychain, "Reload credentials" in the UI (or `SIGHUP`) re-reads it without a restart; the fingerprint change is recorded. | Must |
| FR-HLTH-24 | The fix text for every Keychain credential state names the Keychain item, the provider's key page, and a copyable `security add-generic-password -U -s research-mcp/<NAME> -a "$USER" -w` command with no value in it. | Must |
| FR-HLTH-25 | The Google sign-in used by `vertex_search` is a credential with the usual states. It is validated by refreshing the access token (free) and by reading the engine's metadata (free). No sign-in found is `missing`; a refused refresh (for example `invalid_grant` or reauthentication required) is `invalid`; a disabled API or a missing search permission on the engine is `invalid` with that reason. The fix text gives the copyable `gcloud auth application-default login` command and, for permissions, the engine's console page. v2 stores the account email and the token expiry only, never a token. | Must |

### 2.4 Notifications

| ID | Requirement | Priority |
|---|---|---|
| FR-HLTH-30 | Notifications fire on state changes only: a source becomes `down` or `credential_invalid`; a credential reaches 14, 7, 3 and 1 days before expiry; `quota_low`; `deprecated` at 60, 30 and 7 days; a disk warning; the archive folder becomes unavailable; a cache review batch is ready. | Must |
| FR-HLTH-31 | Unresolved issues roll into one daily digest instead of repeating. | Must |
| FR-HLTH-32 | Channels: macOS notification (primary; with `terminal-notifier` installed, clicking opens the matching UI page; the built-in fallback cannot be clicked through); OpenClaw inbox through a configurable webhook whose token is a Keychain item (optional, open decision O5); a UI banner until resolved or acknowledged. Notifications carry no login tokens. | Must |
| FR-HLTH-33 | Quiet hours (default 21:00 to 08:00) hold non-critical notifications for the morning digest. A credential used in the last hour that becomes invalid notifies immediately. | Should |
| FR-HLTH-34 | Notification text never contains a secret value or a full URL with query parameters. | Must |
| FR-HLTH-35 | Every notification is stored with an acknowledged flag and can be snoozed for N days from the UI. | Should |

### 2.5 Doctor and agent access

| ID | Requirement | Priority |
|---|---|---|
| FR-HLTH-40 | `research-mcp doctor [--json] [--notify]` runs every check without the daemon: daemon liveness, Keychain readability, credential validity, source probes, archive folder, disk, schema version and launchd job state. | Must |
| FR-HLTH-41 | Two launchd jobs watch the daemon independently: `doctor --liveness --notify` every 15 minutes (daemon alive, Keychain readable) and the full `doctor --notify` once a day. A notification is sent only when the result changes. | Must |
| FR-HLTH-42 | Agents can read status through the `research://status` and `research://sources` resources and the `ops_status` tool (summary only, no secrets). | Must |
| FR-HLTH-43 | `/healthz` (liveness) and `/readyz` (stores open, scheduler alive, Keychain readable) answer on loopback; `/api/status` returns the full JSON status to an authenticated caller. | Must |

## 3. Acceptance

Tests `AT-HLTH-*` in [TEST-PLAN v3](../../test-plan/TEST-PLAN-v3.md).

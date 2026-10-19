# Component PRD: Local UI (v1)

- **Parent:** [PRD v1](../PRD-v1.md), goal G8
- **Design:** [HLD](../../design/HLD-v1.md) section 8; [LLD](../../design/LLD-v1.md) section 11; [ADR 0010](../../adr/0010-localhost-ui-stack.md)

## 1. Purpose

A lightweight page on the owner's Mac that shows, at a glance, which sources work, which credentials need attention, what is running, and what is in the cache, and lets the owner answer the archive-or-discard review. It is read-mostly: maintenance actions exist but always ask for confirmation.

## 2. Requirements

### 2.1 General

| ID | Requirement | Priority |
|---|---|---|
| FR-UI-01 | Served by the daemon on `127.0.0.1` only, at the same port as the MCP endpoint, under `/ui`. No separate process, no build step, no CDN: server-rendered HTML with a vendored htmx file. | Must |
| FR-UI-02 | Access starts from a one-time token URL that `research-mcp ui` mints at the moment of use (a notification click runs that command); the session is an HttpOnly, SameSite=Strict cookie; tokens never appear in logs or notifications. Host and Origin headers are checked. | Must |
| FR-UI-03 | Every state-changing request carries a CSRF token; every maintenance action shows what it will do and needs explicit confirmation. | Must |
| FR-UI-04 | No page ever shows a secret value; credentials appear as fingerprints and dates. Log lines shown are redacted. | Must |
| FR-UI-05 | Pages refresh live data every 10 seconds (or on a server-sent event) without a full reload. | Should |
| FR-UI-06 | Pages work in Safari and Chrome at laptop width; no JavaScript framework. | Must |
| FR-UI-07 | UI text follows the owner's style: no em dashes or en dashes. | Must |

### 2.2 Pages, in navigation order

| ID | Page | Shows | Actions |
|---|---|---|---|
| FR-UI-10 | **Source board** (home) | One row per source, grouped by group, with a state chip and counts at the top ("31 ok, 2 degraded, 1 expiring, 4 unconfigured"). Per row: last probe, calls in 24 h, error rate, p95 latency, quota remaining and reset, last classified error, fix hint. | Probe now (one or all); open source detail (latency chart, recent errors by correlation id, recent calls); enable or disable. |
| FR-UI-11 | **Credentials** | Per credential: name, sources that use it, required or optional, fingerprint, Keychain modified date, expiry with countdown, `rotate_by`, last validated, state, and the provider's key page link. | Re-check; reload from Keychain; set or clear `rotate_by`; acknowledge; copy the value-free `security` command. Values are never typed into the browser. |
| FR-UI-12 | **Quota** | For metered sources: allowance, used, remaining, reset, projected exhaustion. GitHub remaining per resource. | Edit per-source budget caps (with confirmation). |
| FR-UI-13 | **Jobs** | Running, queued and recent jobs (fetch batch, crawl, archive, reconcile, rebuild, import) with progress, timing and errors. | Cancel; retry; view log for the job. |
| FR-UI-14 | **Cache** | Cached items: title, source, size, fetched, age, days to expiry, state, pinned. Totals by type, growth per day, free disk. A filter box and a search box ("do I already have this?"). | Pin or unpin; archive now; discard (to trash, confirmed); open the original URL. |
| FR-UI-15 | **Cache review** (`/ui/review/<batch_id>`) | The open batch: per item title, citation, size, age, times asked, integrity changes, and the four choices. A note that unanswered items are kept and asked about again in 7 days. | Submit per-item or bulk decisions; the confirmation summarizes what will be archived (and where) and what goes to the trash. |
| FR-UI-16 | **Archive** | Archive target health; catalog of archived items with date, path and copy-citation; records of discarded items; trash with undo. | Change the archive path (confirmed); run reconcile; undo a discard within 7 days; copy citation or BibTeX. |
| FR-UI-17 | **Maintenance** | Last run and result of each check (integrity, orphans, embedding coverage, schema version, dependency audit, state backup); disk panel. | Verify now; rebuild full-text index; re-embed missing; clean orphans; back up state now. All confirmed. |
| FR-UI-18 | **Events and logs** | Notification history with acknowledged state; recent warning and error log lines (redacted), searchable by correlation id, source or tool. | Acknowledge; snooze for N days. |
| FR-UI-19 | **Settings** | Effective configuration (paths, port, thresholds, quiet hours, channels, archive target), which credential references resolve (names only), versions, launchd job state. | Edit thresholds, quiet hours and channels (confirmed); send a test notification. |

## 3. Out of scope

Remote access; multiple users; editing documents; a search interface that replaces the agent (the cache search box is only for "do I already have this?").

## 4. Acceptance

Tests `AT-UI-*` in [TEST-PLAN v1](../../test-plan/TEST-PLAN-v1.md).

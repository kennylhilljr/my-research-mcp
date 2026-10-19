# Component PRD: Migration and Cutover (v2)

- **Parent:** [PRD v2](../PRD-v2.md), milestone M4; supersedes [v1](PRD-migration-v1.md)
- **Design:** [MIGRATION v1](../../migration/MIGRATION-v1.md); [LLD v2](../../design/LLD-v2.md) section 9.6; [ADR 0001](../../adr/0001-new-repo-v1-read-only.md)
- **Review findings addressed:** FUNC-20, FUNC-21, FUNC-22, FUNC-37, OPS-11

## Changes from v1

Owner decisions of 2026-10-19: (1) cache retention is **120 days** instead of 30; (2) **archiving keeps a paper searchable**: only the PDF moves to Google Drive, while its extracted text, chunks and embeddings stay in `cache.db`, so `search_cache` and `read` still work on archived papers; a rebuild job can re-import the archive from Drive. See [ADR 0011](../../adr/0011-archive-keeps-text-searchable-120-day-retention.md).

## 1. Purpose

Move the owner from v1 to v2 without re-entering any credential, without touching v1's data, and with an easy way back until v2 has proven itself.

## 2. Requirements

### 2.1 Credentials

| ID | Requirement | Priority |
|---|---|---|
| FR-MIG-01 | `research-mcp secrets import` finds the v1 server entries in the MCP client configs on the Mac (Claude desktop, Claude Code, OpenClaw), reads the credential values from their `env` blocks, and writes each to the Keychain as `research-mcp/<NAME>`. It prints names, fingerprints and the config file each came from; never values. | Must |
| FR-MIG-02 | When the same name has different values in different configs, the import stops for that name and asks the owner which config wins (by fingerprint), instead of guessing. | Must |
| FR-MIG-03 | Credentials v2 no longer uses (the web-search keys removed under FR-SRC-17) are listed as "not imported" with a note; they are not copied. | Must |
| FR-MIG-04 | The import is idempotent and has a `--dry-run` that shows what would be written. | Must |
| FR-MIG-05 | After cutover, `research-mcp secrets scrub-client-configs` removes the plaintext `env` values from the old v1 entries (with a backup of each file first), on explicit confirmation. | Should |

### 2.2 Optional corpus import

| ID | Requirement | Priority |
|---|---|---|
| FR-MIG-10 | `research-mcp import-legacy <path> [--dry-run] [--mode M]` (M is `cache`, `archive` or `metadata_only`) runs as a job. It opens the v1 database read-only (immutable) and never modifies the v1 folder. | Should |
| FR-MIG-11 | The import normalizes identifiers (arXiv without version, DOI and CORE prefixes, `iam:<project>:<hash>` rows become HTML documents with their URL), merges the 54 duplicate pairs keeping the titled row's metadata, and maps unknown prefixes (`harv...`, `penn...`) to a `legacy` scheme followed by a best-effort lookup. | Should |
| FR-MIG-12 | The import re-extracts the PDFs with the v2 parser and chunker rather than copying v1 chunks, and falls back to v1 chunks only where re-extraction fails. | Should |
| FR-MIG-13 | The default mode is `cache`: every imported item gets a fresh 120-day expiry and goes through the normal review. | Should |
| FR-MIG-14 | The import writes a report (JSON and Markdown) with rows read, works created, merged pairs, unresolved ids, re-extraction failures, chunk counts before and after, and the legacy-id to work-id map. | Should |
| FR-MIG-15 | Running the import is optional; v2 works fully with an empty cache. | Must |

### 2.3 Client cutover and v1 retirement

| ID | Requirement | Priority |
|---|---|---|
| FR-MIG-20 | `research-mcp install --print-client-config` prints, for each client, the server entry that launches `research-mcp stdio` (no secrets). | Must |
| FR-MIG-21 | Cutover adds the v2 entry beside the v1 entry under a new name (`research`), so both can run during a parallel period; the v1 entry is disabled, not deleted, at cutover. | Must |
| FR-MIG-22 | A tool map documents, for each of the 53 v1 tools, the v2 tool and arguments that replace it (or "removed" with the reason), so agent instructions can be updated. | Must |
| FR-MIG-23 | Rollback is re-enabling the v1 entry in the client configs; it needs no data conversion because v1's data is never modified. | Must |
| FR-MIG-24 | v1 is retired (entry removed, repository archived) only after 14 days of daily use on v2 with no fallback, and only on the owner's explicit go-ahead. | Must |

## 3. Acceptance

Tests `AT-MIG-*` in [TEST-PLAN v1](../../test-plan/TEST-PLAN-v1.md), plus the owner check register.

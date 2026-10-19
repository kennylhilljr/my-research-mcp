# Component PRD: Retrieval and Cache (v2)

- **Parent:** [PRD v2](../PRD-v2.md), goals G6 and G7; supersedes [v1](PRD-cache-v1.md)
- **Design:** [HLD v2](../../design/HLD-v2.md) section 6; [LLD v2](../../design/LLD-v2.md) sections 8 and 9; [ADR 0007](../../adr/0007-cache-lifecycle-and-drive-archive.md), [ADR 0008](../../adr/0008-sqlite-stores-and-vectors.md), [ADR 0011](../../adr/0011-archive-keeps-text-searchable-120-day-retention.md)
- **Review findings addressed:** FUNC-08, FUNC-15, FUNC-16, FUNC-22 to FUNC-31, FUNC-33, FUNC-34, FUNC-39, OPS-05, OPS-08, OPS-17, OPS-18, OPS-20, ARCH-11, ARCH-12, ARCH-16

## Changes from v1

Owner decisions of 2026-10-19: (1) cache retention is **120 days** instead of 30; (2) **archiving keeps a paper searchable**: only the PDF moves to Google Drive, while its extracted text, chunks and embeddings stay in `cache.db`, so `search_cache` and `read` still work on archived papers; a rebuild job can re-import the archive from Drive. See [ADR 0011](../../adr/0011-archive-keeps-text-searchable-120-day-retention.md).

## 1. Purpose

Papers and documents are fetched for a one-time need (owner decision D2). The cache makes them readable, searchable and citable for 120 days, then asks the owner whether to archive or discard each one (D3). Archives go to Google Drive (D4) and stay searchable. Nothing is deleted without an answer.

## 2. Requirements

### 2.1 Fetch

| ID | Requirement | Priority |
|---|---|---|
| FR-CACHE-01 | `fetch` takes a work identifier or URL, finds the best legal open-access copy across all sources (preference order configurable: publisher OA, arXiv, PMC, repository, Unpaywall or OpenAlex location, CORE, OSF), downloads it, extracts text, chunks it, embeds it, and returns a document handle with a short summary. | Must |
| FR-CACHE-02 | Every download goes through one safe downloader: https only, every redirect hop re-checked against the source's host policy, public IP addresses only, a byte cap (default 50 MB), a content-type and magic-byte check (`%PDF-` for PDFs), atomic write into the cache folder, and a full SHA-256. | Must |
| FR-CACHE-03 | Credentials are attached only to requests whose origin matches the credential's source (for example the CORE key only to `api.core.ac.uk`). | Must |
| FR-CACHE-04 | Callers cannot choose where files are written or which local files are parsed. All files live under the cache root. | Must |
| FR-CACHE-05 | Every document records provenance: source, final URL, HTTP status, ETag, license, open-access status, fetch time and a fetch recipe that can re-fetch it later. | Must |
| FR-CACHE-06 | A fetch of a work already cached returns the existing document; a fetch of a discarded work creates a new document from its recipe. | Must |
| FR-CACHE-07 | Fetching more than one document, or any crawl, runs as a job that reports progress and can be cancelled. | Must |

### 2.2 Extraction and chunking

| ID | Requirement | Priority |
|---|---|---|
| FR-CACHE-10 | PDF parsing runs in a worker process with limits on CPU time, memory, wall time and page count. A crash or timeout marks the document `extract_failed` without affecting the daemon. | Must |
| FR-CACHE-11 | Chunks target 300 to 500 tokens with 10 to 15% overlap, break on paragraph then sentence boundaries, never cut a word, and carry page range, character offsets and section heading (from the PDF outline when present). | Must |
| FR-CACHE-12 | HTML documents keep heading structure (h1 to h3) and are chunked by section and length. No chunk exceeds the hard cap (default 4,000 characters) whatever the input. | Must |
| FR-CACHE-13 | Documents with no extractable text are flagged `needs_ocr`; OCR itself is out of scope for v1 of v2. | Should |
| FR-CACHE-14 | Extractions record parser, parser version and chunker version so a later chunker can re-extract selectively. | Must |

### 2.3 Reading and local search

| ID | Requirement | Priority |
|---|---|---|
| FR-CACHE-15 | `read` returns a bounded window of a document by page range, section or chunk range, with a cursor for the rest. | Must |
| FR-CACHE-16 | `search_cache` searches cached documents by keyword (BM25), meaning (vectors) or both (hybrid, default, fused by reciprocal rank), optionally restricted to documents or a collection, and returns snippets with page numbers and the embedding coverage. | Must |
| FR-CACHE-17 | Full-text search indexes content, section and title, supports prefix queries, and falls back to a literal match when the query has invalid syntax. | Must |
| FR-CACHE-18 | `library` lists cached items with state, size, age and days to expiry, and reports totals. | Must |

### 2.4 Embeddings

| ID | Requirement | Priority |
|---|---|---|
| FR-CACHE-20 | Every chunk is embedded at fetch time (in the worker), so coverage is complete without a manual step. | Must |
| FR-CACHE-21 | Embeddings are keyed by chunk content hash and model, store the model name and dimension, and are removed with their chunks. | Must |
| FR-CACHE-22 | Queries use the model's query encoding and passages its passage encoding. | Must |
| FR-CACHE-23 | Embeddings live in the cache database file; no persisted approximate index that can corrupt on an unclean shutdown. | Must |
| FR-CACHE-24 | Embeddings are an optional extra; without it, `search_cache` runs keyword-only and says so. | Should |

### 2.5 Lifecycle and owner review

States: `cached`, `pinned`, `expiring`, `kept`, `archived`, `discarded`.

| ID | Requirement | Priority |
|---|---|---|
| FR-CACHE-30 | A fetched document is `cached` with `expires_at` = fetch time + 120 days (`cache.retention_days`, fixed from fetch per open decision O7). | Must |
| FR-CACHE-31 | A daily check at 09:00 local time moves documents whose expiry is within 3 days, plus `kept` items due for another ask, into one review batch and marks them `expiring`. | Must |
| FR-CACHE-32 | A review batch produces one macOS notification ("6 cached papers expire Friday: review") that opens the UI review page, and one optional OpenClaw inbox message. | Must |
| FR-CACHE-33 | For each item in a batch the owner can choose Archive, Discard, Keep (another 120 days), or Pin; bulk choices apply to the whole batch. | Must |
| FR-CACHE-34 | **No answer means keep.** An unanswered item stays with its files, becomes `kept`, and is asked about again after 7 days. Nothing is ever deleted without a recorded owner decision. | Must |
| FR-CACHE-35 | The owner can also answer from an agent chat: `cache_review_list(batch_id)` and `cache_review_decide(batch_id, decisions)`. Decisions must name an open batch and only its items; MCP decisions are recorded as made by an agent on the owner's behalf; a discard through MCP goes to the 7-day trash and immediately notifies the owner with an undo link. No other MCP tool can discard. | Must |
| FR-CACHE-36 | Discard removes the file, chunks and embeddings after a 7-day trash period (undo possible in the UI), and keeps the work's metadata, citation snapshot and fetch recipe. The owner is notified 24 hours before items leave the trash. A file shared with another live document is never removed. | Must |
| FR-CACHE-37 | Pin keeps an item indefinitely; unpin returns it to `cached` with a fresh 120 days. | Must |
| FR-CACHE-38 | A review shows, for each item: title, citation, source, size, age, times already asked, last access, and any integrity change since caching (for example a retraction). | Must |

### 2.6 Archive to Google Drive

| ID | Requirement | Priority |
|---|---|---|
| FR-CACHE-45 | The archive target is the locally synced Google Drive folder, default `My Drive/Research Archive/<year>/`; the daemon finds the `GoogleDrive-*` folder and the owner confirms it once. No Drive API credential is used. The first write happens during install, in the foreground, so any macOS privacy prompt appears while the owner is present. | Must |
| FR-CACHE-46 | Archiving writes the file and a sidecar `<slug>.meta.json` (title, authors, CSL-JSON, formatted citation, BibTeX, source, identifiers, original URL, fetched and archived times, SHA-256, size). | Must |
| FR-CACHE-47 | The archive copy is written to a temporary name, flushed, renamed, read back and checked (size and SHA-256) before the cached copy of the file is removed. | Must |
| FR-CACHE-48 | If the Drive folder is missing or not writable, the item is archived to a local fallback folder (default `~/Research Archive/<year>/`), marked as fallback, and the owner is warned; a reconcile job moves fallback items to Drive when the folder is healthy again. | Must |
| FR-CACHE-49 | Archived items stay findable and **searchable**: only the file moves to Drive; the extracted text, chunks, full-text index entries and embeddings stay in `cache.db`, so `search_cache` and `read` work on archived items exactly as on cached ones. `library` and `get_work` report the archive path and date; `cite` works from the stored metadata. | Must |
| FR-CACHE-50 | The archive folder's health (exists, writable, macOS privacy access granted, Drive app running, free space) is a monitored target on the source board. Each archived file's upload state is checked; an archive not uploaded within 24 hours is reported. | Must |

### 2.7 Collections, crawl jobs, disk

| ID | Requirement | Priority |
|---|---|---|
| FR-CACHE-55 | Collections are named sets of works; a collection pins its members only when created with pinning on (off by default, so collections do not turn the cache into a library). `collections` supports create, add, remove, list, show and export (through `cite`). | Should |
| FR-CACHE-56 | `crawl_site` crawls an allowlisted docs site into the cache as a job, under the same 120-day lifecycle. | Should |
| FR-CACHE-57 | Disk use is measured every 15 minutes: cache size by type (files, index, embeddings, model cache, trash) and free space on the cache and archive volumes. Warning above 5 GB of cache or below 15 GB free; critical below 5 GB free. | Must |
| FR-CACHE-58 | Integrity checks run daily: database quick check, full-text index integrity, files missing on disk, orphan files and orphan embeddings. Failures appear on the Maintenance page with a fix action that needs confirmation. | Must |
| FR-CACHE-51 | A rebuild job (`research-mcp archive reindex`) walks the Drive archive folder and, for each file with a sidecar, re-creates or verifies its work, identifiers and archived document, re-extracting text and embeddings where they are missing, so the searchable archive can be rebuilt if `cache.db` is lost. It never modifies the Drive files. | Should |
| FR-CACHE-52 | `search_cache` results say whether each hit is cached, pinned or archived; filtering by state is possible. Reading the original PDF of an archived item points to its Drive path. | Must |
| FR-CACHE-59 | Cache data (`cache.db`, stored files, trash) lives in Application Support, not in `~/Library/Caches`, so macOS or cleaning tools cannot purge pinned, kept or expiring items without an answer. `cache.db` is backed up nightly with `state.db`. | Must |

## 3. Out of scope

OCR; annotation and highlighting; syncing the archive back into the cache automatically; a reference-manager feature set.

## 4. Acceptance

Tests `AT-CACHE-*` in [TEST-PLAN v1](../../test-plan/TEST-PLAN-v1.md).

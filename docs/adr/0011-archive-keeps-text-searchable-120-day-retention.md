# ADR 0011: 120-day retention; archived papers stay searchable

- **Status:** Accepted (owner decision, 2026-10-19)
- **Date:** 2026-10-19
- **Amends:** [ADR 0007](0007-cache-lifecycle-and-drive-archive.md)

## Context

ADR 0007 set a 30-day cache and an archive that moved a paper's file to Google Drive and deleted its extracted text, chunks and embeddings. That left a gap for papers the owner wants to keep: once archived, an agent could still find and cite them by metadata but could not search inside them without fetching them again. The owner also judged 30 days too short.

## Decision

1. `cache.retention_days` is 120, counted from fetch. Keep, unpin, undo and collection changes all grant a fresh 120 days. The review still runs 3 days before expiry and re-asks unanswered items after 7 days.
2. Archiving moves only the file to the Drive sync folder (with its sidecar). The document's extraction, chunks, full-text entries and embeddings stay in `cache.db`, so `search_cache` and `read` work on archived documents. `search_cache` can filter by state.
3. A rebuild job (`archive reindex`) can re-create the searchable archive from the Drive folder and its sidecars if `cache.db` is lost. It never modifies the Drive files.
4. Pin and archive now differ only in where the file lives: pin keeps it on the Mac, archive keeps it in Drive. Both are searchable and never expire.

## Consequences

- `cache.db` grows with every archived paper's text and vectors. At the v1 corpus size that is tens of megabytes (about 34 MB of index for 186 papers, against 307 MB of PDFs); disk monitoring covers it, and `cache.db` is already backed up nightly.
- No separate archive database is needed; SQLite remains the only store (ADR 0008). DuckDB is not used for storage.
- The archive is recoverable from two places: the nightly `cache.db` backup and the Drive folder itself.

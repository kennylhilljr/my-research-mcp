# ADR 0008: Two SQLite files; vectors stored in SQLite

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

v1 uses a SQLite FTS index plus a separate DuckDB file with a persisted HNSW index, which DuckDB warns can corrupt after an unclean shutdown (OPS-17); vectors are keyed by row ids that change on re-index, orphaning them (FUNC-30). The two files share no transaction.

## Decision

v2 uses two SQLite databases in WAL mode with versioned migrations, both under `~/Library/Application Support/research-mcp/` and both backed up nightly: `state.db` (credential metadata, health, telemetry, jobs, notifications, a copy of review events) and `cache.db` (works, documents and their lifecycle including pins, decisions and archive paths, chunks, FTS5 with external content, embeddings, collections, and an outbox that feeds review events to `state.db`). Nothing the lifecycle depends on lives in `~/Library/Caches`, which macOS and cleaning tools may purge; only the re-downloadable embedding model does. Embeddings are float32 BLOBs keyed by chunk content hash and model, in `cache.db`, removed with their chunks. Similarity search is exact (NumPy) at personal scale; `sqlite-vec` may replace it behind the same function later. DuckDB is not a store; if used at all, it is internal and locked down (ADR 0009).

## Consequences

- One transaction covers chunks and their vectors.
- Exact search is simple and correct for tens of thousands of chunks; it would need an index at millions.
- Wiping stored files loses nothing that cannot be re-fetched; the lifecycle record (pins, decisions, archive catalog, citations) survives in `cache.db` and its backups.

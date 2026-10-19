# ADR 0009: No free-form SQL; fetched content is labeled untrusted

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

v1's `analytics_sql` and `dataset_query` let the calling model read arbitrary local files (verified with `read_text`, list-form `read_csv` and `glob`), including the client configs that hold API keys (OPS-01, OPS-02). Fetched documents can carry prompt injection that steers a model toward such tools (OPS-10).

## Decision

v2 exposes no SQL tool (open decision O4 may add a narrow, parameterized one later). No tool reads local files outside the cache root or accepts a caller-chosen path. Any internal DuckDB connection runs with external access off, allowed directories limited, extension auto-install and auto-load off, and configuration locked. All fetched text is returned in an `untrusted` envelope with its source, the server instructions tell clients to treat it as data, every tool declares MCP annotations, no tool hard-deletes, and review decisions through MCP must name an open batch.

## Consequences

- The largest v1 risk is removed.
- Ad hoc analytics over the cache are no longer available to agents; the UI and `library stats` cover the common questions.

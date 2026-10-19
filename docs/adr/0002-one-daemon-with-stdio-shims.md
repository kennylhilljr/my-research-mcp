# ADR 0002: One daemon per Mac; clients use a stdio shim

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

In v1 each MCP client starts its own server process (OPS-12). Rate limiters are per process, so arXiv's one request per 3 seconds is broken as soon as two clients search; DuckDB's single-writer lock makes the embeddings file fail in the second client; health, quota and job state cannot be shared; the embedding model loads once per client.

## Decision

A single resident daemon, `research-mcpd`, runs under a launchd LaunchAgent with `KeepAlive`. It owns every HTTP client, rate limiter, store, the scheduler, the MCP endpoint (streamable HTTP on `127.0.0.1`) and the UI. MCP clients launch `research-mcp stdio`, a thin relay that connects to the daemon with a bearer token and asks launchd to start it if needed. Every client goes through the shim, so no client config holds the token. The MCP endpoint runs in stateless mode, so a daemon restart never strands a client session.

## Consequences

- Global rate limits, one health picture, one job queue, one cache.
- A second moving part (the shim) and a background service to manage; `doctor` and a 15-minute launchd watchdog cover both.
- The daemon must be robust: worker isolation for parsing and strict async rules (ADR 0005).
- The daemon token lives in the Keychain (ADR 0003).

# ADR 0005: Async I/O end to end; CPU work in worker processes

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

FastMCP runs synchronous tools inline on the event loop. In v1, 49 of 53 tools are synchronous and the 4 async ones call synchronous HTTP underneath, so every call blocks every other call, and fan-out across sources is impossible (ARCH-03, OPS-13). PDF parsing with PyMuPDF can hang or crash on hostile input (OPS-20).

## Decision

All network I/O uses one shared `httpx.AsyncClient`. Federation uses structured concurrency with per-source timeouts and an overall deadline. PDF parsing, HTML extraction, chunking and embedding run in one short-lived subprocess per task (not a `ProcessPoolExecutor`, which on macOS cannot enforce memory limits or kill a running task), with a CPU rlimit, an RSS watchdog and a wall-clock kill. SQLite access goes through store classes with a single writer per database, off the event loop. Long operations are jobs with progress and cancellation. Ruff's ASYNC rules are enforced in CI.

## Consequences

- Concurrent searches across many sources become possible.
- A crash in a parser kills a worker, not the daemon.
- Async code needs discipline; the conformance suite and ASYNC lint rules catch blocking calls.

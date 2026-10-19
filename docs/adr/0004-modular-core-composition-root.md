# ADR 0004: Modular core built by one composition root; no work at import

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

v1 configures logging, reads 17 environment variables and creates the MCP server at import time (ARCH-13); two configuration systems coexist (ARCH-14); every concern lives in one module (ARCH-01).

## Decision

The code is layered (core, platform, sources, services, transport) with dependencies pointing down only. One function, `build_app(settings)`, creates every component inside a lifespan that opens and closes them. Importing any module performs no I/O, reads no environment and configures no logging. One `Settings` model, with per-source sections derived from each `SourceSpec`, is the only configuration path.

## Consequences

- Components are testable in isolation; a second app instance can be built in tests.
- Module size stays small (target under about 400 lines).
- A little more wiring code than a single module.

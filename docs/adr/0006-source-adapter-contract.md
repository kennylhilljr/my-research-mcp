# ADR 0006: Every source is an adapter with a declarative SourceSpec

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

Breadth is the product (owner decision D1), yet v1 has no source abstraction: DSpace is eight copy-paste tools, rate limits exist for 3 of about 25 sources, and adding a source touches five places (ARCH-04, ARCH-06).

## Decision

Each source is one module with a `SourceSpec` (capabilities, identifier schemes, auth, rate policy, timeouts, page size, extras, probe, shutdown date, default enabled) and an adapter that only translates between the upstream API and normalized models. Adapters never retry, sleep, read secrets or write files; the shared HTTP client does those things using the spec. A registry discovers adapters and builds configured instances (one DSpace adapter, four repository instances). Every adapter declares the hosts it may call, ships seven recorded fixtures and passes one conformance suite. Policy types (auth, rate, probe) live in `core/specs.py` so the HTTP layer does not depend on the source layer.

## Consequences

- Adding a source is one module and one fixtures folder; discovery is automatic.
- Health probes, quotas and credential checks are declared, not coded per source.
- Federated search and the UI work from the registry, so new sources appear everywhere automatically.
- Adapters with unusual upstreams (upstream MCP servers, crawled docs sites) need small base classes of their own.

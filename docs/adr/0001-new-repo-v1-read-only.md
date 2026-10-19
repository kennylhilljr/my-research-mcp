# ADR 0001: v2 is a new repository; v1 stays read-only and running until cutover

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

v1 (`my-research-mcp-server`) is in daily use by three MCP clients. Its main module is a 4,613-line monolith, and a better foundation in `research_mcp/` was never wired in (review ARCH-01, ARCH-02). Rebuilding in place would mix two architectures in one history and break the clients during the rebuild.

## Decision

v2 is built in a new repository, `my-research-mcp` (local; no remote until the owner asks; named `my-research-mcp-v2` until 2026-10-19). No v2 code is written into the v1 tree. v2 reads v1 only through (1) the optional legacy import, which opens the v1 index database immutable and read-only, and (2) the credential import, which reads the v1 client config `env` blocks once on the Mac and writes only to the Keychain.

v1 keeps running under its existing client entries until cutover (milestone M4). At cutover its entries are disabled, not deleted.

## Consequences

- Clean history and a clean dependency set.
- The owner keeps a working tool throughout the rebuild.
- Rollback is re-enabling the v1 client entry; no data conversion is needed because v1 data is never modified.
- Two server processes may run side by side during the parallel period; v2's global rate limits do not cover v1's calls, so the parallel period should be short.

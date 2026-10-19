# ADR 0007: 30-day cache with owner review; archive to the Google Drive sync folder

- **Status:** Proposed; amended by [ADR 0011](0011-archive-keeps-text-searchable-120-day-retention.md) (120-day retention; archived papers keep their searchable text)
- **Date:** 2026-10-19

## Context

The owner fetches papers for one-time needs (D2) and wants them kept 30 days, then to be asked whether to archive or discard each one, with nothing deleted silently (D3). The archive should be Google Drive (D4). v1 keeps everything forever, with duplicates and no cleanup.

## Decision

Fetched documents enter the cache with a fixed expiry 30 days after fetch. A daily check groups documents expiring within 3 days into one review batch and sends one notification. The owner chooses archive, discard, keep or pin per item, in the UI or through two batch-scoped MCP tools; MCP decisions are recorded as agent decisions, and any MCP discard is announced to the owner at once with an undo link. Unanswered items are kept and asked about again after 7 days; nothing is deleted without a recorded decision. Discards go to a 7-day trash, and the owner is notified 24 hours before anything leaves it; a file shared with another live document is never removed. Archives are written to the locally synced Google Drive folder (`My Drive/Research Archive/<year>/`) with a sidecar metadata file, verified by reading back, and only then removed from the cache; if the folder is unavailable a local fallback is used and reconciled later. Work metadata, the citation snapshot and the fetch recipe outlive the files.

## Consequences

- The cache stays small and purposeful; archived papers live where the owner's other files live.
- No Google OAuth credential is needed. The trade-offs: a local write means Drive will upload, not that it has (upload state is checked through the file provider and a stall is reported), and macOS privacy controls may require one-time consent, which install requests in the foreground.
- Review fatigue is possible; batching and the keep default keep it low.

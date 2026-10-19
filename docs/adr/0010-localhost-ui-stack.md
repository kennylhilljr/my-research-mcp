# ADR 0010: The UI is server-rendered inside the daemon

- **Status:** Proposed (accepted when the owner approves PRD v1)
- **Date:** 2026-10-19

## Context

The owner wants a lightweight UI for sources, health, credentials, jobs and the cache (D6). The daemon already serves HTTP through Starlette (an MCP SDK dependency).

## Decision

The UI is a set of Starlette routes and Jinja2 templates served by the daemon on `127.0.0.1` under `/ui`, with one vendored htmx file for partial refresh and confirmation dialogs, and no JavaScript build. Pages read the same services the MCP tools use. Sessions start from a one-time token URL; writes need a CSRF token and confirmation; no page shows a secret.

## Consequences

- No second process, API or build chain to maintain.
- Interactivity is limited to what htmx does well, which fits a read-mostly status page.
- Rejected: Streamlit, Gradio and NiceGUI (second process or their own app model) and a React single-page app (build chain, more upkeep).

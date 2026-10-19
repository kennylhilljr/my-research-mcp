# Research MCP v2

A personal MCP server that searches, fetches, reads and cites research from 42 sources (including optional, capped web search) through one MCP server (17 tools). It shows the health of every source and every credential, and keeps fetched papers in a 120-day cache that asks before anything is deleted; archived papers move to Google Drive and stay searchable.

**Status:** design drafted for owner review; no code yet. Source inventory (generated in M0): [docs/generated/sources.md](docs/generated/sources.md). v1 (`my-research-mcp-server`) stays in use until cutover.

| Document | What it is |
|---|---|
| [docs/review/REVIEW-v1.md](docs/review/REVIEW-v1.md) | Deep review of v1 and the owner decisions behind v2 |
| [docs/prd/PRD-v3.md](docs/prd/PRD-v3.md) | Parent PRD; components are in `docs/prd/components/` (use the newest `-vN` of each) |
| [docs/design/HLD-v3.md](docs/design/HLD-v3.md) | High-level design |
| [docs/design/LLD-v3.md](docs/design/LLD-v3.md) | Low-level design; owns all names and the work breakdown |
| [docs/design/prompts-v2.md](docs/design/prompts-v2.md) | MCP prompt texts (registered in M1) |
| [docs/test-plan/TEST-PLAN-v3.md](docs/test-plan/TEST-PLAN-v3.md) | Acceptance tests, traceability and milestone gates (partly generated) |
| [docs/adr/](docs/adr/) | Architecture decisions 0001 to 0012 |
| [docs/migration/MIGRATION-v2.md](docs/migration/MIGRATION-v2.md) | Cutover plan and the v1 to v2 tool map |
| [.orchestration/PILOT-M0.md](.orchestration/PILOT-M0.md) | How to build M0 through the ECC orchestrator |

Earlier versions are kept for history; the running M0 plan cites LLD v2 and TEST-PLAN v2, whose M0 content is unchanged in v3. Generated files: `docs/test-plan/TEST-PLAN-v3.md` sections 4 to 6 and Appendix A (`tools/gen_test_plan.py`), and `.orchestration/plan-m0.json` (`tools/gen_m0_plan.py`).

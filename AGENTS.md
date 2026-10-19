# Agent instructions for Research MCP v2

- Read the newest PRD (`docs/prd/PRD-v2.md` today), the newest version of the relevant component PRD, and the section of the newest LLD (`docs/design/LLD-v2.md`) your work unit names before changing anything. The LLD owns names: modules, classes, tables, settings keys, Keychain items, routes.
- Work only inside this repository. v1 (`my-research-mcp-server`) and `~/arxiv-papers` are read-only: never edit them, and never open the v1 database except through the legacy import job.
- Never read the Keychain, client configs or any real credential. Use `FakeProvider`, recorded fixtures and the fakes in `research_mcp.testing`. Tests must pass with the network blocked.
- Never print, log, commit or put in fixtures any secret, token or password. Fixtures are recorded with credentials removed.
- Adapters (`src/research_mcp/sources/`) only translate. No HTTP library imports, no sleeping, no retries, no secrets, no file writes in adapters.
- No tool may block the event loop; CPU work goes to worker subprocesses (`platform/workers.py`).
- Every change needs tests. Put the acceptance test id first in the test docstring (`"""AT-SRCH-11: ..."""`). Test ids are in the newest test plan (`docs/test-plan/TEST-PLAN-v2.md`).
- The source inventory is generated: `docs/generated/sources.md`.
- Test folders have no `__init__.py` (pytest runs in importlib mode); never add one.
- Keep `tools/ci.sh --python-only` green. Do not edit generated files by hand; run their generators.
- Docs are versioned: to revise a document, add a new `-vN` file and update links; do not overwrite earlier versions.
- Do not use em dashes or en dashes in prose, comments or UI text.
- Never push, and never run `security`, `launchctl` or anything that changes the Mac outside this repository.

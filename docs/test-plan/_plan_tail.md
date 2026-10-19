## 7. Fixtures and fakes

| Fake or fixture | Location | Used by |
|---|---|---|
| Recorded source fixtures (seven per adapter) | `tests/sources/<id>/fixtures/` | conformance, adapter tests, federation |
| `FakeProvider` (secrets; records argv) | `src/research_mcp/platform/secrets.py` | all tests that need credentials |
| `FakeClock`, fake `Sleeper` | `src/research_mcp/testing/clock.py` | rate limits, retries, scheduler, lifecycle, notifications |
| Fake adapters (configurable latency, failures) | `src/research_mcp/testing/adapters.py` | registry, conformance, federation |
| `FakeLaunchctl` | `src/research_mcp/testing/launchctl.py` | shim, install, doctor |
| `FakeNotifier`, fake resolver | `src/research_mcp/testing/notifier.py`, test-local | notifications (M1), downloader |
| In-memory MCP client | `tests/contract/conftest.py` | contract tests |
| Synthetic v1 database | `tests/migration/fixtures/make_v1_db.py` | legacy import (reproduces 54 pairs, 10 URL rows, harv and penn ids) |
| Hostile PDF corpus | `tests/fixtures/pdf/hostile/` | AT-SEC-23 |
| Temp "Drive" folder | pytest `tmp_path` laid out as `CloudStorage/GoogleDrive-test/My Drive` | archive tests |

## 8. Milestone exit gates

| Milestone | Gate |
|---|---|
| M0 | Every M0 test in Appendix A passes; full `tools/ci.sh` green (lint, strict mypy, coverage 85% on `src/`, build, `--help`); owner checks OC-01 and OC-02. |
| M1 | All M1 tests pass; all 38 sources registered and passing conformance; OC-03, OC-08 (once a remote exists), OC-11, OC-12. |
| M2 | All M2 tests pass, including the hostile PDF corpus; OC-04, OC-10 and OC-13. |
| M3 | All M3 tests pass; OC-05 and OC-09. |
| M4 | All M4 tests pass; OC-06 then OC-07. |

## 9. Open issues found while writing this plan

1. The in-memory MCP client in `mcp<2` exposes structured content differently across minor versions; AT-SRCH-20 pins the SDK version in the lock file and checks the field the pinned version uses.
2. AT-PLAT-03 (no work at import) cannot rely on audit hooks for environment reads, so the subprocess replaces `os.environ` with a recording mapping and filters `open` events to non-module files.
3. OC-12 depends on upstream latency the project does not control; if it fails, the deadline or default source set is tuned rather than the gate removed.

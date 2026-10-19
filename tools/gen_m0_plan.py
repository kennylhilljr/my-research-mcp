"""Builds .orchestration/plan-m0.json from LLD section 12.3 and TEST-PLAN Appendix A."""
import json, re, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
lld = (ROOT / "docs/design/LLD-v2.md").read_text()
plan = (ROOT / "docs/test-plan/TEST-PLAN-v2.md").read_text()

sec = lld.split("### 12.3", 1)[1].split("### 12.4", 1)[0]
rows = [l for l in sec.splitlines() if l.startswith("| M0-")]
appx = plan.split("## Appendix A", 1)[1].split("\n## ", 1)[0]
tests = {m.group(1): m.group(2) for m in re.finditer(r"^\| (M0-\d\d) \| ([^|]+) \|", appx, re.M)}

PKG = "src/research_mcp/"
def expand(path):
    path = path.strip().strip("`")
    if path.startswith(("src/", "tests/", "tools/", "docs/", ".github/")) or path in ("pyproject.toml", "uv.lock", ".python-version"):
        return path
    return PKG + path

units = []
for r in rows:
    cells = [c.strip() for c in r.strip("|").split("|")]
    uid, title, impl, files, deps, risk = cells
    file_list = []
    for f in re.findall(r"`([^`]+)`", files):
        f = f if not f.endswith("/*") else f[:-2] + "/search_ok.json"
        file_list.append(expand(f))
    fixture_dirs = [f for f in file_list if f.endswith("fixtures/search_ok.json")]
    for fd in fixture_dirs:
        base = fd.rsplit("/", 1)[0]
        ext = "xml" if "/arxiv/" in base else "json"
        file_list.remove(fd)
        for n in (f"search_ok.{ext}", f"search_empty.{ext}", f"get_ok.{ext}", "err_429.json", "err_5xx.json", f"malformed.{ext}", "oversize.marker"):
            file_list.append(f"{base}/{n}")
    dep_list = [] if deps == "none" else [d.strip() for d in deps.split(",")]
    at = tests[uid].strip()
    test_files = [f for f in file_list if f.startswith("tests/") and f.endswith(".py") and "/test_" in f]
    if uid == "M0-01":
        cmds = ["uv sync --frozen", "uv run pytest tests/unit -q"]
    else:
        cmds = ["uv run pytest " + " ".join(test_files) + " -q"]
    m = re.match(r"src/research_mcp/sources/(\w+)\.py$", file_list[0])
    if m and m.group(1) not in ("base", "registry"):
        cmds.append(f"uv run pytest tests/sources/test_conformance.py -k {m.group(1)} -q")
    cmds.append("tools/ci.sh --python-only")
    tier = {"low": 0, "medium": 1, "high": 2}[risk]
    desc = (f"Read AGENTS.md first. Build exactly this work unit as defined in docs/design/LLD-v2.md section 12.3 "
            f"(unit {uid}), following the LLD sections it implements ({impl}) and the names the LLD owns. "
            f"Write the acceptance tests the test plan assigns to this unit (docs/test-plan/TEST-PLAN-v2.md Appendix A): {at}; "
            "put each test id first in the test docstring per test plan section 1.3. Keep tools/ci.sh --python-only green; gates run commands "
            "directly without a shell, so tools/ci.sh must stay executable with a #!/usr/bin/env bash line. Do not add __init__.py files under tests/ and do not edit pyproject.toml, uv.lock or any package __init__.py (M0-01 owns them). Do not touch the v1 "
            "repository (my-research-mcp-server) or ~/arxiv-papers, never read real credentials or the Keychain, and use fakes "
            "and recorded fixtures for every external system; tests must pass with the network blocked.")
    units.append({
        "schema_version": "1.0", "id": uid, "title": title, "description": desc,
        "depends_on": dep_list, "scope": {"files": file_list},
        "acceptance": {"commands": cmds}, "risk": risk,
        "capabilities": {"network": True, "secrets": []},
        "routing": {"initial_tier": tier, "maximum_tier": 2, "reviewer_must_differ_from_author": True},
        "budget": {"attempts": 3, "minutes": 240, "maximum_cost_usd": 10.0},
        "rollback": "revert the unit branch; nothing outside this repository changes",
    })
out = ROOT / ".orchestration/plan-m0.json"
text = json.dumps({"units": units}, indent=1) + "\n"
if "--check" in sys.argv:
    sys.exit(0 if out.exists() and out.read_text() == text else 1)
out.write_text(text)
print(len(units), "units")

"""Package version, packaging metadata and the CI script."""

from __future__ import annotations

import os
import stat
import tomllib
from importlib.metadata import version
from pathlib import Path
from typing import Any

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

import research_mcp
from research_mcp.version import __version__

REPO = Path(__file__).resolve().parents[2]


def _pyproject() -> dict[str, Any]:
    with (REPO / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _names(requirements: list[str]) -> set[str]:
    return {canonicalize_name(Requirement(text).name) for text in requirements}


def test_version_is_3x_and_matches_metadata() -> None:
    """AT-PLAT-01: package version is 3.x and matches pyproject and installed metadata."""
    assert __version__.split(".")[0] == "3"
    assert research_mcp.__version__ == __version__
    assert _pyproject()["project"]["version"] == __version__
    assert version("research-mcp") == __version__


def test_ci_script_is_executable_bash() -> None:
    """AT-PLAT-02: tools/ci.sh exists, is executable and starts with #!/usr/bin/env bash."""
    script = REPO / "tools" / "ci.sh"
    assert script.is_file()
    assert script.stat().st_mode & stat.S_IXUSR
    assert os.access(script, os.X_OK)
    assert script.read_text(encoding="utf-8").splitlines()[0] == "#!/usr/bin/env bash"


def test_heavy_dependencies_are_extras() -> None:
    """AT-PLAT-04: pyproject declares extras pdf and embeddings; base excludes heavy deps."""
    project = _pyproject()["project"]
    extras = project["optional-dependencies"]
    assert "pymupdf" in _names(extras["pdf"])
    assert {"fastembed", "numpy"} <= _names(extras["embeddings"])

    base = _names(project["dependencies"])
    assert base.isdisjoint({"pymupdf", "fastembed", "duckdb"})

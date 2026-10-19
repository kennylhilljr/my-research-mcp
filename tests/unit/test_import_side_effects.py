"""Importing research_mcp does no work: no environment, files, sockets, processes or logging.

The check runs in a fresh interpreter. Third-party dependencies are imported first and
pydantic is primed, so their own import-time work is not recorded. Then os.environ is
replaced by a recording mapping (audit hooks do not see environment reads), an audit hook
is installed and the package and every submodule are imported. An event counts against
the package when the first frame outside the standard library is a file of the package,
so work done by an already-imported dependency on its own behalf is not counted.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from importlib.metadata import packages_distributions, requires
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PROBE = r"""
import functools
import importlib
import importlib.machinery
import importlib.util
import json
import logging
import os
import pkgutil
import sys
import sysconfig
from collections.abc import MutableMapping

target, third_party = sys.argv[1], json.loads(sys.argv[2])
for name in third_party:
    importlib.import_module(name)

import pydantic


class _Prime(pydantic.BaseModel):
    value: int = 0


_Prime(value=1).model_dump_json()

target_dir = os.path.realpath(os.path.dirname(importlib.util.find_spec(target).origin)) + os.sep
paths = sysconfig.get_paths()
stdlib = tuple(os.path.realpath(paths[k]) + os.sep for k in ("stdlib", "platstdlib"))
site = tuple(os.path.realpath(paths[k]) + os.sep for k in ("purelib", "platlib"))
module_suffixes = tuple(importlib.machinery.all_suffixes()) + (".pyc", ".pth")
events = []


@functools.lru_cache(maxsize=None)
def _kind_of_file(filename):
    if filename.startswith("<frozen"):
        return "stdlib"
    path = os.path.realpath(filename)
    if path.startswith(target_dir):
        return "target"
    if path.startswith(stdlib) and not path.startswith(site):
        return "stdlib"
    return "other"


def _attributed(frame):
    while frame is not None:
        kind = _kind_of_file(frame.f_code.co_filename)
        if kind != "stdlib":
            return kind == "target"
        frame = frame.f_back
    return False


class RecordingEnviron(MutableMapping):
    def __init__(self, real):
        self._real = real

    def _note(self, key):
        if _attributed(sys._getframe(2)):
            events.append(["env", str(key)])

    def __getitem__(self, key):
        self._note(key)
        return self._real[key]

    def __contains__(self, key):
        self._note(key)
        return key in self._real

    def __setitem__(self, key, value):
        self._note(key)
        self._real[key] = value

    def __delitem__(self, key):
        self._note(key)
        del self._real[key]

    def __iter__(self):
        self._note("*")
        return iter(self._real)

    def __len__(self):
        self._note("*")
        return len(self._real)

    def copy(self):
        self._note("*")
        return dict(self._real)


KINDS = {
    "open": "open",
    "socket.__new__": "socket",
    "socket.connect": "socket",
    "socket.bind": "socket",
    "subprocess.Popen": "subprocess",
    "os.system": "subprocess",
    "os.posix_spawn": "subprocess",
    "os.exec": "subprocess",
    "os.fork": "subprocess",
    "os.forkpty": "subprocess",
    "os.mkdir": "mkdir",
}


def _hook(event, args):
    kind = KINDS.get(event)
    if kind is None or not _attributed(sys._getframe(1)):
        return
    if kind == "open":
        path = args[0]
        if not isinstance(path, (str, bytes)):
            return
        path = os.fsdecode(path)
        if path.endswith(module_suffixes):
            return
        events.append([kind, path])
        return
    events.append([kind, event])


real_add_handler = logging.Logger.addHandler


def _add_handler(self, handler):
    if _attributed(sys._getframe(1)):
        events.append(["logging", self.name])
    return real_add_handler(self, handler)


os.environ = RecordingEnviron(os.environ)
logging.Logger.addHandler = _add_handler
sys.addaudithook(_hook)

imported = [target]
package = importlib.import_module(target)


def _raise(name):
    raise ImportError(name)


for info in pkgutil.walk_packages(package.__path__, target + ".", onerror=_raise):
    importlib.import_module(info.name)
    imported.append(info.name)

sys.stdout.write(json.dumps({"events": events, "imported": imported}))
"""

DIRTY_PACKAGE = """
import logging
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(__file__)
os.environ.get("HOME")
open(os.path.join(HERE, "data.txt")).close()
socket.socket().close()
subprocess.run([sys.executable, "-c", "pass"], check=True)
os.mkdir(os.path.join(HERE, "made"))
logging.getLogger("probe_dirty").addHandler(logging.NullHandler())
"""


def _third_party_modules() -> list[str]:
    """Top-level modules of every base (non-extra) dependency of research-mcp."""
    wanted = set()
    for text in requires("research-mcp") or []:
        requirement = Requirement(text)
        if requirement.marker is not None and "extra" in str(requirement.marker):
            continue
        wanted.add(canonicalize_name(requirement.name))
    modules = {
        module
        for module, dists in packages_distributions().items()
        if module.isidentifier()
        and not module.startswith("_")
        and any(canonicalize_name(dist) in wanted for dist in dists)
    }
    return sorted(modules)


def _probe(target: str, pythonpath: Path | None = None) -> dict[str, list[object]]:
    env = dict(os.environ)
    if pythonpath is not None:
        env["PYTHONPATH"] = str(pythonpath)
    completed = subprocess.run(  # noqa: S603 (fixed argv, our own interpreter)
        [sys.executable, "-B", "-c", PROBE, target, json.dumps(_third_party_modules())],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result: dict[str, list[object]] = json.loads(completed.stdout)
    return result


def test_third_party_modules_cover_base_dependencies() -> None:
    """AT-PLAT-03: the probe pre-imports the base dependencies, not the heavy extras."""
    modules = _third_party_modules()
    assert {"httpx", "mcp", "pydantic", "pydantic_settings", "ulid", "tomli_w"} <= set(modules)
    assert {"fitz", "pymupdf", "fastembed", "numpy"}.isdisjoint(modules)


def test_probe_detects_import_side_effects(tmp_path: Path) -> None:
    """AT-PLAT-03: the recorder catches each kind of import-time work it checks for."""
    package = tmp_path / "probe_dirty"
    package.mkdir()
    (package / "__init__.py").write_text(textwrap.dedent(DIRTY_PACKAGE), encoding="utf-8")
    (package / "data.txt").write_text("x", encoding="utf-8")

    result = _probe("probe_dirty", pythonpath=tmp_path)

    kinds = {event[0] for event in result["events"]}  # type: ignore[index]
    assert kinds == {"env", "open", "socket", "subprocess", "mkdir", "logging"}


def test_importing_research_mcp_does_no_work() -> None:
    """AT-PLAT-03: importing research_mcp and every submodule does no I/O at import.

    No environment read, no non-module file opened, no socket, no subprocess, no
    directory made and no logging handler added.
    """
    result = _probe("research_mcp")

    assert result["events"] == []
    imported = set(result["imported"])
    for package in (
        "core",
        "platform",
        "sources",
        "services",
        "mcp_app",
        "ui",
        "testing",
        "packaging",
        "version",
    ):
        assert f"research_mcp.{package}" in imported

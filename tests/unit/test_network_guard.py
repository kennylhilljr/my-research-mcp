"""The socket guard in tests/conftest.py and the default deselection of live tests."""

from __future__ import annotations

import socket
import tomllib
from pathlib import Path

import httpx
import pytest
import tomli_w

REPO = Path(__file__).resolve().parents[2]

# TEST-NET-1 (RFC 5737): never routed, so a guard failure cannot reach a real host.
UNROUTABLE = "192.0.2.1"


def test_blocks_non_loopback_connect() -> None:
    """AT-PLAT-05: a test not marked live cannot open a non-loopback connection."""
    with (
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
        pytest.raises(RuntimeError, match="network blocked"),
    ):
        sock.settimeout(0.5)
        sock.connect((UNROUTABLE, 80))

    with pytest.raises(RuntimeError, match="network blocked"):
        socket.create_connection((UNROUTABLE, 80), timeout=0.5)


def test_blocks_name_lookup() -> None:
    """AT-PLAT-05: a test not marked live cannot resolve a public host name."""
    with pytest.raises(RuntimeError, match="network blocked"):
        socket.getaddrinfo("example.org", 443)


def _blocked(error: BaseException) -> bool:
    if isinstance(error, BaseExceptionGroup):
        return any(_blocked(inner) for inner in error.exceptions)
    return isinstance(error, RuntimeError) and "network blocked" in str(error)


async def test_blocks_async_http_client() -> None:
    """AT-PLAT-05: the guard also stops httpx on the event loop."""
    async with httpx.AsyncClient(timeout=0.5) as client:
        # anyio races connection attempts and may wrap the guard error in a group.
        with pytest.raises((RuntimeError, BaseExceptionGroup)) as info:
            await client.get(f"http://{UNROUTABLE}/")
    assert _blocked(info.value)


def test_allows_loopback() -> None:
    """AT-PLAT-05: loopback connections stay open for local test servers."""
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
        with socket.create_connection(("localhost", port), timeout=2) as client:
            peer, _ = server.accept()
            with peer:
                client.sendall(b"ok")
                assert peer.recv(2) == b"ok"


def _copy_pytest_setup(pytester: pytest.Pytester) -> None:
    with (REPO / "pyproject.toml").open("rb") as handle:
        ini_options = tomllib.load(handle)["tool"]["pytest"]["ini_options"]
    pytester.makefile(
        ".toml", pyproject=tomli_w.dumps({"tool": {"pytest": {"ini_options": ini_options}}})
    )
    pytester.makeconftest((REPO / "tests" / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(
        test_markers="""
        import socket

        import pytest

        ORIGINAL_CONNECT = socket.socket.connect


        @pytest.mark.live
        def test_live():
            assert socket.socket.connect is ORIGINAL_CONNECT


        def test_offline():
            assert socket.socket.connect is not ORIGINAL_CONNECT
        """
    )


def test_live_tests_deselected_by_default(pytester: pytest.Pytester) -> None:
    """AT-PLAT-05: live tests are deselected by default; the guard covers the rest."""
    _copy_pytest_setup(pytester)
    result = pytester.runpytest_subprocess("-v")
    result.assert_outcomes(passed=1, deselected=1)
    result.stdout.fnmatch_lines(["*test_offline PASSED*"])


def test_live_tests_run_unguarded_when_selected(pytester: pytest.Pytester) -> None:
    """AT-PLAT-05: with -m live, live tests run without the socket guard."""
    _copy_pytest_setup(pytester)
    result = pytester.runpytest_subprocess("-m", "live", "-v")
    result.assert_outcomes(passed=1, deselected=1)
    result.stdout.fnmatch_lines(["*test_live PASSED*"])

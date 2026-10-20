"""The socket guard in tests/conftest.py and the default deselection of live tests."""

from __future__ import annotations

import socket
import textwrap
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


@pytest.mark.parametrize("name", ["gethostbyname", "gethostbyname_ex", "gethostbyaddr"])
def test_blocks_legacy_resolver_calls(name: str) -> None:
    """AT-PLAT-05: the older resolver functions are blocked like getaddrinfo."""
    with pytest.raises(RuntimeError, match="network blocked"):
        getattr(socket, name)("example.org")


def test_blocks_datagrams_to_non_loopback() -> None:
    """AT-PLAT-05: sendto and sendmsg with a non-loopback address are blocked."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        with pytest.raises(RuntimeError, match="network blocked"):
            sock.sendto(b"x", (UNROUTABLE, 53))
        with pytest.raises(RuntimeError, match="network blocked"):
            sock.sendto(b"x", 0, (UNROUTABLE, 53))
        with pytest.raises(RuntimeError, match="network blocked"):
            sock.sendmsg([b"x"], [], 0, (UNROUTABLE, 53))


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


def test_passes_loopback_through() -> None:
    """AT-PLAT-05: the guard hands loopback connects to the OS instead of blocking them."""
    for host, family in (("127.0.0.1", socket.AF_INET), ("localhost", socket.AF_INET)):
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            # Port 9 (discard) normally refuses, and a sandbox may deny the connect. Either
            # way connect_ex returns the OS error code; the guard would raise instead.
            assert isinstance(sock.connect_ex((host, 9)), int)


def test_allows_loopback() -> None:
    """AT-PLAT-05: loopback connections stay open for local test servers."""
    try:
        server = socket.create_server(("127.0.0.1", 0))
    except PermissionError:
        pytest.skip("this sandbox denies binding to 127.0.0.1")
    with server:
        port = server.getsockname()[1]
        with socket.create_connection(("localhost", port), timeout=2) as client:
            peer, _ = server.accept()
            with peer:
                client.sendall(b"ok")
                assert peer.recv(2) == b"ok"


def _copy_pytest_setup(pytester: pytest.Pytester, **files: str) -> None:
    with (REPO / "pyproject.toml").open("rb") as handle:
        ini_options = tomllib.load(handle)["tool"]["pytest"]["ini_options"]
    pytester.makefile(
        ".toml", pyproject=tomli_w.dumps({"tool": {"pytest": {"ini_options": ini_options}}})
    )
    pytester.makeconftest((REPO / "tests" / "conftest.py").read_text(encoding="utf-8"))
    pytester.makepyfile(**{name: textwrap.dedent(body) for name, body in files.items()})


MARKER_TESTS = f"""
import contextlib
import socket

import pytest


def _udp_connect():
    # A UDP connect only sets the default peer; it sends nothing.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("{UNROUTABLE}", 9))


@pytest.mark.live
def test_live():
    with contextlib.suppress(OSError):
        _udp_connect()


def test_offline():
    with pytest.raises(RuntimeError, match="network blocked"):
        _udp_connect()
"""


def test_live_tests_deselected_by_default(pytester: pytest.Pytester) -> None:
    """AT-PLAT-05: live tests are deselected by default; the guard covers the rest."""
    _copy_pytest_setup(pytester, test_markers=MARKER_TESTS)
    result = pytester.runpytest_subprocess("-v")
    result.assert_outcomes(passed=1, deselected=1)
    result.stdout.fnmatch_lines(["*test_offline PASSED*"])


def test_live_tests_run_unguarded_when_selected(pytester: pytest.Pytester) -> None:
    """AT-PLAT-05: with -m live, live tests run without the socket guard."""
    _copy_pytest_setup(pytester, test_markers=MARKER_TESTS)
    result = pytester.runpytest_subprocess("-m", "live", "-v")
    result.assert_outcomes(passed=1, deselected=1)
    result.stdout.fnmatch_lines(["*test_live PASSED*"])


def test_guard_covers_session_fixtures(pytester: pytest.Pytester) -> None:
    """AT-PLAT-05: a session-scoped fixture set up for an offline test is guarded."""
    _copy_pytest_setup(
        pytester,
        test_session="""
        import socket

        import pytest


        @pytest.fixture(scope="session")
        def remote():
            return socket.gethostbyname("example.org")


        def test_uses_remote(remote):
            pass
        """,
    )
    result = pytester.runpytest_subprocess("-v")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*network blocked in tests: lookup of 'example.org'*"])


def test_guard_covers_collection(pytester: pytest.Pytester) -> None:
    """AT-PLAT-05: network calls made while a test module is imported are guarded."""
    _copy_pytest_setup(
        pytester,
        test_import_time="""
        import socket

        ADDRESS = socket.getaddrinfo("example.org", 443)


        def test_nothing():
            pass
        """,
    )
    result = pytester.runpytest_subprocess("-v")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*network blocked in tests: lookup of 'example.org'*"])

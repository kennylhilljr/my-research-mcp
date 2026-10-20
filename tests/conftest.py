"""Shared pytest setup: every test not marked ``live`` runs with the network blocked.

The guard is installed in ``pytest_configure``, before collection, so module level code,
session fixtures and every test share it. It is lifted only while a test marked ``live``
runs. Loopback stays open so tests can run local servers. Live tests are deselected by
default through ``-m 'not live'`` in pyproject.toml and run only with ``pytest -m live``.

The guard patches this process only. It stops accidents in Python code; it is not a
sandbox, and child processes started by a test do not inherit it.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Generator
from typing import Any

import pytest

pytest_plugins = ["pytester"]


class NetworkBlockedError(RuntimeError):
    """A test that is not marked live tried to reach a non-loopback host."""


_live_running = False
_originals: dict[tuple[object, str], Any] = {}


def _is_loopback_host(host: object) -> bool:
    if host is None:  # getaddrinfo(None, ...) asks for a local address
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped.is_loopback
    return address.is_loopback


def _check(family: int, address: Any) -> None:
    if _live_running or family == getattr(socket, "AF_UNIX", None):
        return
    host = address[0] if isinstance(address, tuple) and address else address
    if not _is_loopback_host(host):
        raise NetworkBlockedError(
            f"network blocked in tests: {address!r}; mark the test live to allow it"
        )


def _check_lookup(host: object) -> None:
    if not _live_running and not _is_loopback_host(host):
        raise NetworkBlockedError(
            f"network blocked in tests: lookup of {host!r}; mark the test live to allow it"
        )


def _guard_lookup(real: Callable[..., Any]) -> Callable[..., Any]:
    def lookup(host: Any, *args: Any, **kwargs: Any) -> Any:
        _check_lookup(host)
        return real(host, *args, **kwargs)

    return lookup


def _install_guard() -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_sendmsg = socket.socket.sendmsg

    def connect(self: socket.socket, address: Any) -> None:
        _check(self.family, address)
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        _check(self.family, address)
        return real_connect_ex(self, address)

    def sendto(self: socket.socket, data: Any, *args: Any) -> int:
        if args:  # sendto(data, address) or sendto(data, flags, address)
            _check(self.family, args[-1])
        return real_sendto(self, data, *args)

    def sendmsg(self: socket.socket, buffers: Any, *args: Any) -> int:
        if len(args) >= 3 and args[2] is not None:  # (ancdata, flags, address)
            _check(self.family, args[2])
        return real_sendmsg(self, buffers, *args)

    patches: dict[tuple[object, str], Any] = {
        (socket.socket, "connect"): connect,
        (socket.socket, "connect_ex"): connect_ex,
        (socket.socket, "sendto"): sendto,
        (socket.socket, "sendmsg"): sendmsg,
    }
    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
        patches[(socket, name)] = _guard_lookup(getattr(socket, name))
    for (owner, name), replacement in patches.items():
        _originals[(owner, name)] = getattr(owner, name)
        setattr(owner, name, replacement)


def _remove_guard() -> None:
    for (owner, name), original in _originals.items():
        setattr(owner, name, original)
    _originals.clear()


def pytest_configure(config: pytest.Config) -> None:
    _install_guard()


def pytest_unconfigure(config: pytest.Config) -> None:
    _remove_guard()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(
    item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, object, object]:
    global _live_running
    _live_running = item.get_closest_marker("live") is not None
    try:
        return (yield)
    finally:
        _live_running = False

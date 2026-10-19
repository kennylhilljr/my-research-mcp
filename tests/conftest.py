"""Shared pytest setup: every test not marked ``live`` runs with the network blocked.

Loopback stays open so tests can run local servers. Live tests are deselected by default
through ``-m 'not live'`` in pyproject.toml and run only with ``pytest -m live``.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import pytest

pytest_plugins = ["pytester"]


class NetworkBlockedError(RuntimeError):
    """A test that is not marked live tried to reach a non-loopback host."""


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
    if family == getattr(socket, "AF_UNIX", None):
        return
    host = address[0] if isinstance(address, tuple) and address else address
    if not _is_loopback_host(host):
        raise NetworkBlockedError(
            f"network blocked in tests: {address!r}; mark the test live to allow it"
        )


@pytest.fixture(autouse=True)
def _block_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("live") is not None:
        return

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_sendto = socket.socket.sendto
    real_getaddrinfo = socket.getaddrinfo

    def connect(self: socket.socket, address: Any) -> None:
        _check(self.family, address)
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        _check(self.family, address)
        return real_connect_ex(self, address)

    def sendto(self: socket.socket, data: Any, *args: Any) -> int:
        _check(self.family, args[-1])
        return real_sendto(self, data, *args)

    def getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_loopback_host(host):
            raise NetworkBlockedError(
                f"network blocked in tests: lookup of {host!r}; mark the test live to allow it"
            )
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket.socket, "sendto", sendto)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)

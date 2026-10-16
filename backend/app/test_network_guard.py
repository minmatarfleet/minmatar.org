"""
Block outbound network access from the unit test suite.

Tests that reach the internet are slow (django-eveuniverse resolves a
type with ~100 sequential ESI calls) and fail whenever ESI or zKill is
down. Seed local rows or mock the client instead.
"""

import ipaddress
import socket

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


class NetworkAccessBlocked(RuntimeError):
    pass


def _is_local(address) -> bool:
    if not isinstance(address, tuple):
        # AF_UNIX sockets (e.g. multiprocessing) are always local.
        return True
    host = address[0]
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _guarded(real):
    def connect(sock, address):
        if not _is_local(address):
            raise NetworkAccessBlocked(
                f"Refusing network access to {address!r} during unit tests. "
                "Seed local data or mock the client."
            )
        return real(sock, address)

    return connect


def install():
    socket.socket.connect = _guarded(_real_connect)
    socket.socket.connect_ex = _guarded(_real_connect_ex)

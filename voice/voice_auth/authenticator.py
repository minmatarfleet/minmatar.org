"""The login decision Murmur asks for on every connect.

Pure logic, so it is tested without Ice; ``main.py`` wraps it in the Ice
``ServerAuthenticator`` servant.

Murmur's return codes: a user id (>= 0) accepts; -1 refuses ("Wrong
certificate or password"); -3 means "can not be verified currently, try
again later". -2 (fall through to Murmur's own user database) is never
returned: nobody is registered on the server.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from voice_auth.records import Unavailable

logger = logging.getLogger(__name__)

REFUSE = -1
UNAVAILABLE = -3
SUPERUSER = "SuperUser"


@dataclass
class Decision:
    result: int
    name: str = ""
    groups: list[str] = field(default_factory=list)
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.result >= 0

    def as_ice(self):
        return self.result, self.name, list(self.groups)


def _accept(record) -> Decision:
    if not record.get("admitted") or record.get("banned"):
        return Decision(REFUSE, reason=record.get("reason") or "no_access")
    identity_id = record.get("identity_id")
    if identity_id is None:
        return Decision(REFUSE, reason="no_identity")
    return Decision(
        int(identity_id),
        name=record.get("display_name") or "",
        groups=list(record.get("server_groups") or []),
        reason="ok",
    )


def authenticate(name: str, password: str, cert_hash: str, store) -> Decision:
    """Bound certificate first, then a one-time connect token."""
    if (name or "").strip().lower() == SUPERUSER.lower():
        return Decision(REFUSE, reason="superuser")
    try:
        if cert_hash:
            record = store.by_certificate(cert_hash)
            if record is not None:
                # A bound certificate decides the identity; a spent token
                # sent alongside it is ignored.
                return _accept(record)
        if password:
            record = store.redeem(password, cert_hash or "")
            if record is not None:
                return _accept(record)
    except Unavailable as exc:
        logger.warning("Voice access could not be checked: %s", exc)
        return Decision(UNAVAILABLE, reason="unavailable")
    return Decision(REFUSE, reason="unknown")

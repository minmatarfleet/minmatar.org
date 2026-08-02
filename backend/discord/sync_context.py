"""Thread-local flag to skip Discord m2m sync during intentional offboard."""

from __future__ import annotations

import threading
from contextlib import contextmanager

_local = threading.local()


def is_discord_group_sync_disabled() -> bool:
    return bool(getattr(_local, "disabled", False))


@contextmanager
def disable_discord_group_sync():
    """
    Temporarily skip user↔group Discord role sync.

    Use around offboard deletes so cascading M2M clears do not call Discord
    (roles are cleaned via DiscordUser pre_delete / explicit role delete).
    Always restores the previous flag so workers are never permanently muted.
    """
    previous = getattr(_local, "disabled", False)
    _local.disabled = True
    try:
        yield
    finally:
        _local.disabled = previous

"""Shared helpers for alliance health endpoints."""

from alliance.helpers.health import latest_snapshot
from app.errors import ErrorResponse


def require_snapshot():
    """Return (snapshot, None) or (None, 503 error tuple)."""
    snap = latest_snapshot()
    if snap is None or not snap.payload:
        return None, (
            503,
            ErrorResponse(
                detail="Alliance health snapshot not ready. Run refresh_alliance_health."
            ),
        )
    return snap, None

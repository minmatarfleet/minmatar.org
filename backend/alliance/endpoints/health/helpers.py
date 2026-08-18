"""Shared helpers for alliance health endpoints."""

from alliance.helpers.access import (
    can_view_health,
    ceo_corp_ids,
    is_alliance_executor,
    officer_corp_ids,
    viewer_home_corp_id,
)
from alliance.helpers.health import latest_snapshot
from alliance.endpoints.health.schemas import ViewerContext
from app.errors import ErrorResponse
from groups.helpers.feature_access import (
    FEATURE_DENIED_DETAIL,
    can_use_feature,
)


def require_health_view(user):
    """Return None if allowed, else (403, body)."""
    if can_view_health(user):
        return None
    return 403, {"detail": FEATURE_DENIED_DETAIL, "feature": "alliance.health"}


def viewer_context(user) -> ViewerContext:
    corps = sorted(officer_corp_ids(user))
    ceo_corps = sorted(ceo_corp_ids(user))
    executor = is_alliance_executor(user)
    staff_only = can_use_feature(user, "alliance.health") and not corps
    alliance_wide = executor or staff_only
    return ViewerContext(
        alliance_wide=alliance_wide,
        home_corp_id=viewer_home_corp_id(user),
        can_mutate=executor or bool(corps),
        can_leave_any=bool(user and user.is_superuser),
        officer_corp_ids=corps,
        ceo_corp_ids=ceo_corps,
    )


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

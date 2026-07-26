"""Shared auth checks for planner endpoints."""

from app.errors import ErrorResponse


def auth_required_for_character(request, character_id):
    """Character skill lookups require a logged-in user.

    Returns ``None`` when allowed, or ``(status, ErrorResponse)``.
    """
    if character_id is None:
        return None
    auth = getattr(request, "auth", None)
    if auth is None or getattr(auth, "is_anonymous", True):
        return 401, ErrorResponse(
            detail="Authentication required to use character skills"
        )
    return None

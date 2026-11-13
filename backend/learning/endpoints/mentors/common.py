"""Shared lookups and error handling for the mentor endpoints."""

from __future__ import annotations

from functools import wraps

from authentication import is_service_account
from discord.models import DiscordUser
from learning.mentors.service import MentorError
from learning.mentors import views
from learning.models import MentorClass, MentorRequest

ERRORS = {400: dict, 403: dict, 404: dict}


def handles_errors(view):
    """Turn MentorError into (status, {"detail": ...})."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except MentorError as exc:
            return exc.status_code, {"detail": str(exc)}

    return wrapper


def get_request(request_id: int) -> MentorRequest:
    req = (
        MentorRequest.objects.select_related(
            "mentor", "mentor__user", "mentor_class", "pilot"
        )
        .filter(pk=request_id)
        .first()
    )
    if req is None:
        raise MentorError("Class not found.", 404)
    return req


def get_class(class_id: int) -> MentorClass:
    mc = MentorClass.objects.filter(pk=class_id).first()
    if mc is None:
        raise MentorError("Class not found.", 404)
    return mc


def require_request_access(user) -> None:
    if not views.can_request(user):
        raise MentorError("Mentors are for alliance pilots.", 403)


def require_manage(user) -> None:
    if not views.can_manage(user):
        raise MentorError("Learning managers only.", 403)


def discord_user(request, discord_user_id: int):
    """The site user behind a bot button press (bot calls only)."""
    if not is_service_account(request.user):
        raise MentorError("Only the Discord bot can do that.", 403)
    row = (
        DiscordUser.objects.select_related("user")
        .filter(id=discord_user_id)
        .first()
    )
    if row is None or row.user is None:
        raise MentorError(
            "Link your Discord account on the website first.", 403
        )
    return row.user


def ok(message: str, status: str = "ok") -> tuple[int, dict]:
    return 200, {"status": status, "message": message}

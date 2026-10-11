"""Who can see corporation admin (roster, activity, Discord status)."""

from django.contrib.auth.models import User

from eveonline.models import EveCorporation
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team


def user_is_ceo(user: User, corporation: EveCorporation) -> bool:
    ceo = corporation.ceo
    if ceo is None:
        return False
    if ceo.user_id == user.id:
        return True
    token = ceo.token
    return bool(token and token.user_id == user.id)


def can_manage_corporation(user: User, corporation: EveCorporation) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if user_is_ceo(user, corporation):
        return True
    if any(
        director.user_id == user.id for director in corporation.directors.all()
    ):
        return True
    if user_in_team(user, PEOPLE_TEAM) or user_in_team(user, TECH_TEAM):
        return True
    return False


def _holds_role(user: User, characters) -> bool:
    return (
        characters.filter(user_id=user.id).exists()
        or characters.filter(token__user_id=user.id).exists()
    )


def user_is_recruiter(user: User, corporation: EveCorporation) -> bool:
    return _holds_role(user, corporation.recruiters)


def user_is_director(user: User, corporation: EveCorporation) -> bool:
    return _holds_role(user, corporation.directors)


def can_view_corporation_members(
    user: User, corporation: EveCorporation
) -> bool:
    """Members tab: corp leadership, recruiters, People and Tech teams,
    and site superusers."""
    if can_manage_corporation(user, corporation):
        return True
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user.is_superuser or user_is_recruiter(user, corporation)


def can_view_member_characters(
    user: User, corporation: EveCorporation
) -> bool:
    """Which characters belong to whom: CEO, directors, recruiters, superusers.

    Everyone else who can see the roster gets one row per person with a
    character count, never the characters themselves.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user_is_ceo(user, corporation):
        return True
    return user_is_director(user, corporation) or user_is_recruiter(
        user, corporation
    )

"""Who can see corporation admin (roster, activity, Discord status)."""

from django.contrib.auth.models import User

from eveonline.helpers.characters.identity import owned_by_q
from eveonline.models import EveCharacter, EveCorporation
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team


def _owns(user: User, character: EveCharacter | None) -> bool:
    """Ownership rule from eveonline.helpers.characters.identity: the
    character's user, or its token's user only when it has no user."""
    if character is None:
        return False
    if character.user_id:
        return character.user_id == user.id
    token = character.token
    return bool(token and token.user_id == user.id)


def ceo_user(corporation: EveCorporation) -> User | None:
    """The site user who owns the CEO character, matched like user_is_ceo."""
    ceo = corporation.ceo
    if ceo is None:
        return None
    if ceo.user_id:
        return ceo.user
    token = ceo.token
    return token.user if token and token.user_id else None


def user_is_ceo(user: User, corporation: EveCorporation) -> bool:
    return _owns(user, corporation.ceo)


def can_manage_corporation(user: User, corporation: EveCorporation) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if user_is_ceo(user, corporation):
        return True
    if any(_owns(user, director) for director in corporation.directors.all()):
        return True
    if user_in_team(user, PEOPLE_TEAM) or user_in_team(user, TECH_TEAM):
        return True
    return False


def _holds_role(user: User, characters) -> bool:
    return characters.filter(owned_by_q(user.id)).exists()


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


def can_manage_corporation_projects(
    user: User, corporation: EveCorporation
) -> bool:
    """CEO and directors put the corporation's projects toward campaigns."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user_is_ceo(user, corporation) or user_is_director(
        user, corporation
    )


def can_view_corporation_projects(
    user: User, corporation: EveCorporation
) -> bool:
    """Projects tab: corp leadership, People and Tech teams, superusers."""
    if can_manage_corporation(user, corporation):
        return True
    return bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and user.is_superuser
    )

"""Who can view alliance health and change community status."""

from django.contrib.auth.models import User

from eveonline.helpers.alliances import alliance_corporations
from eveonline.helpers.characters import user_primary_character
from groups.helpers.feature_access import can_use_feature

EXECUTOR_FEATURE = "alliance.health.executor"

def mfa_corporation_qs():
    return alliance_corporations(include_holding_corporation=False)


def ceo_corp_ids(user: User) -> set[int]:
    """MFA corporation_ids where the user is CEO (not director)."""
    if not user or not user.is_authenticated:
        return set()
    return set(
        mfa_corporation_qs()
        .filter(ceo__user=user)
        .values_list("corporation_id", flat=True)
    )


def officer_corp_ids(user: User) -> set[int]:
    """MFA corporation_ids where the user is CEO or director."""
    if not user or not user.is_authenticated:
        return set()
    director_ids = set(
        mfa_corporation_qs()
        .filter(directors__user=user)
        .values_list("corporation_id", flat=True)
    )
    return ceo_corp_ids(user) | director_ids


def is_alliance_executor(user: User) -> bool:
    """People Team (and superusers) act alliance-wide.

    Through the feature evaluator, so a member who is on leave or whose
    account is deactivated does not.
    """
    if not user or not user.is_authenticated:
        return False
    return can_use_feature(user, EXECUTOR_FEATURE, allow_legacy=False)


def can_view_health(user: User) -> bool:
    if is_alliance_executor(user):
        return True
    if can_use_feature(user, "alliance.health"):
        return True
    return bool(officer_corp_ids(user))


def viewer_home_corp_id(user: User) -> int | None:
    """Default corp filter: primary MFA corp, else a corp they officer."""
    if not user or not user.is_authenticated:
        return None
    mfa_ids = set(
        mfa_corporation_qs().values_list("corporation_id", flat=True)
    )
    primary = user_primary_character(user)
    if primary and primary.corporation_id in mfa_ids:
        return primary.corporation_id
    ids = officer_corp_ids(user)
    if len(ids) == 1:
        return next(iter(ids))
    if primary and primary.corporation_id in ids:
        return primary.corporation_id
    if ids:
        return sorted(ids)[0]
    return None


def can_mutate_status(actor: User, target: User) -> bool:
    """Promote (and other People/officer mutations) for a target member."""
    if is_alliance_executor(actor):
        return True
    primary = user_primary_character(target)
    if primary is None or primary.corporation_id is None:
        return False
    return primary.corporation_id in officer_corp_ids(actor)


def can_put_on_leave(actor: User, target: User) -> bool:
    """Put on leave: superuser, or CEO of the target's primary corp."""
    if not actor or not actor.is_authenticated:
        return False
    if actor.is_superuser:
        return True
    primary = user_primary_character(target)
    if primary is None or primary.corporation_id is None:
        return False
    return primary.corporation_id in ceo_corp_ids(actor)

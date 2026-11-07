"""Doctrine/fitting protection tiers and Django permission checks."""

from django.contrib.auth import get_user_model

from fittings.models import (
    DOCTRINE_TYPE_CAPITAL,
    DOCTRINE_TYPE_EXPERIMENTAL,
    DOCTRINE_TYPE_NON_STRATEGIC,
    DOCTRINE_TYPE_STRATEGIC,
    EveDoctrine,
    EveDoctrineFitting,
    PROTECTION_TIER_NON_STRATEGIC,
    PROTECTION_TIER_STRATEGIC,
)
from groups.helpers.feature_access import can_use_feature

user_model = get_user_model()


def protection_tier_for_doctrine(doctrine: EveDoctrine) -> str | None:
    return protection_tier_for_doctrine_type(doctrine.type)


_TIER_RANK = {
    None: 0,
    PROTECTION_TIER_NON_STRATEGIC: 1,
    PROTECTION_TIER_STRATEGIC: 2,
}


def stricter_tier(*tiers: str | None) -> str | None:
    """The most protected of the given tiers (None = no review)."""
    return max(tiers, key=lambda tier: _TIER_RANK.get(tier, 0), default=None)


def tier_covers(request_tier: str | None, needed: str | None) -> bool:
    return _TIER_RANK.get(request_tier, 0) >= _TIER_RANK.get(needed, 0)


def doctrine_change_tier(stored_type: str | None, new_type: str) -> str | None:
    """
    Review tier for moving a doctrine from stored_type to new_type.

    A category change is reviewed at the stricter of the two tiers, so
    Strategic -> Experimental still needs a strategic approver and
    Experimental -> Strategic cannot skip review.
    """
    return stricter_tier(
        protection_tier_for_doctrine_type(stored_type or ""),
        protection_tier_for_doctrine_type(new_type or ""),
    )


def effective_protection_tier(fitting) -> str | None:
    types = set(
        EveDoctrineFitting.objects.filter(fitting=fitting).values_list(
            "doctrine__type", flat=True
        )
    )
    types.discard(DOCTRINE_TYPE_EXPERIMENTAL)
    if types & {DOCTRINE_TYPE_STRATEGIC, DOCTRINE_TYPE_CAPITAL}:
        return PROTECTION_TIER_STRATEGIC
    if DOCTRINE_TYPE_NON_STRATEGIC in types:
        return PROTECTION_TIER_NON_STRATEGIC
    return None


def _tier_can_approve_doctrine(user, tier: str) -> bool:
    if tier == PROTECTION_TIER_NON_STRATEGIC:
        return user.has_perm(
            "fittings.approve_doctrine_non_strategic"
        ) or user.has_perm("fittings.approve_doctrine_strategic")
    if tier == PROTECTION_TIER_STRATEGIC:
        return user.has_perm("fittings.approve_doctrine_strategic")
    return False


def can_approve_doctrine_request(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    if _tier_can_approve_doctrine(user, tier):
        return True
    return can_use_feature(user, "fittings.doctrine.approve")


def _tier_can_approve_fitting(user, tier: str) -> bool:
    if tier == PROTECTION_TIER_NON_STRATEGIC:
        return user.has_perm(
            "fittings.approve_doctrine_fitting_non_strategic"
        ) or user.has_perm("fittings.approve_doctrine_fitting_strategic")
    if tier == PROTECTION_TIER_STRATEGIC:
        return user.has_perm("fittings.approve_doctrine_fitting_strategic")
    return False


def can_approve_fitting_request(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    if _tier_can_approve_fitting(user, tier):
        return True
    return can_use_feature(user, "fittings.doctrine.approve")


def can_propose_doctrine_change(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    if user.has_perm(f"fittings.change_doctrine_{tier}"):
        return True
    return can_use_feature(user, "fittings.doctrine.propose")


def can_propose_fitting_change(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    if user.has_perm(f"fittings.change_doctrine_fitting_{tier}"):
        return True
    return can_use_feature(user, "fittings.doctrine.propose")


can_publish_doctrine_change = can_propose_doctrine_change
can_publish_fitting_change = can_propose_fitting_change


def protection_tier_for_doctrine_type(doctrine_type: str) -> str | None:
    """Protection tier implied by a doctrine type value (for payload validation)."""
    if doctrine_type == DOCTRINE_TYPE_EXPERIMENTAL:
        return None
    if doctrine_type == DOCTRINE_TYPE_NON_STRATEGIC:
        return PROTECTION_TIER_NON_STRATEGIC
    if doctrine_type in (DOCTRINE_TYPE_STRATEGIC, DOCTRINE_TYPE_CAPITAL):
        # Capital fittings are expensive to get wrong: same gate as strategic.
        return PROTECTION_TIER_STRATEGIC
    return None

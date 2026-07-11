"""Doctrine/fitting protection tiers and Django permission checks."""

from django.contrib.auth import get_user_model

from fittings.models import (
    DOCTRINE_TYPE_EXPERIMENTAL,
    DOCTRINE_TYPE_NON_STRATEGIC,
    DOCTRINE_TYPE_STRATEGIC,
    EveDoctrine,
    EveDoctrineFitting,
    PROTECTION_TIER_NON_STRATEGIC,
    PROTECTION_TIER_STRATEGIC,
)

user_model = get_user_model()


def protection_tier_for_doctrine(doctrine: EveDoctrine) -> str | None:
    if doctrine.type == DOCTRINE_TYPE_EXPERIMENTAL:
        return None
    if doctrine.type == DOCTRINE_TYPE_NON_STRATEGIC:
        return PROTECTION_TIER_NON_STRATEGIC
    if doctrine.type == DOCTRINE_TYPE_STRATEGIC:
        return PROTECTION_TIER_STRATEGIC
    return None


def effective_protection_tier(fitting) -> str | None:
    types = set(
        EveDoctrineFitting.objects.filter(fitting=fitting).values_list(
            "doctrine__type", flat=True
        )
    )
    types.discard(DOCTRINE_TYPE_EXPERIMENTAL)
    if DOCTRINE_TYPE_STRATEGIC in types:
        return PROTECTION_TIER_STRATEGIC
    if DOCTRINE_TYPE_NON_STRATEGIC in types:
        return PROTECTION_TIER_NON_STRATEGIC
    return None


def can_approve_doctrine_request(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    if tier == PROTECTION_TIER_NON_STRATEGIC:
        return user.has_perm(
            "fittings.approve_doctrine_non_strategic"
        ) or user.has_perm("fittings.approve_doctrine_strategic")
    if tier == PROTECTION_TIER_STRATEGIC:
        return user.has_perm("fittings.approve_doctrine_strategic")
    return False


def can_approve_fitting_request(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    if tier == PROTECTION_TIER_NON_STRATEGIC:
        return user.has_perm(
            "fittings.approve_doctrine_fitting_non_strategic"
        ) or user.has_perm("fittings.approve_doctrine_fitting_strategic")
    if tier == PROTECTION_TIER_STRATEGIC:
        return user.has_perm("fittings.approve_doctrine_fitting_strategic")
    return False


def can_propose_doctrine_change(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    return user.has_perm(f"fittings.change_doctrine_{tier}")


def can_propose_fitting_change(user, tier: str) -> bool:
    if user and user.is_superuser:
        return True
    return user.has_perm(f"fittings.change_doctrine_fitting_{tier}")


can_publish_doctrine_change = can_propose_doctrine_change
can_publish_fitting_change = can_propose_fitting_change


def protection_tier_for_doctrine_type(doctrine_type: str) -> str | None:
    """Protection tier implied by a doctrine type value (for payload validation)."""
    if doctrine_type == DOCTRINE_TYPE_EXPERIMENTAL:
        return None
    if doctrine_type == DOCTRINE_TYPE_NON_STRATEGIC:
        return PROTECTION_TIER_NON_STRATEGIC
    if doctrine_type == DOCTRINE_TYPE_STRATEGIC:
        return PROTECTION_TIER_STRATEGIC
    return None


def users_who_can_approve_doctrine_request(tier: str):
    recipients = []
    for user in user_model.objects.filter(is_active=True, is_staff=True):
        if can_approve_doctrine_request(user, tier):
            recipients.append(user)
    return recipients


def users_who_can_approve_fitting_request(tier: str):
    recipients = []
    for user in user_model.objects.filter(is_active=True, is_staff=True):
        if can_approve_fitting_request(user, tier):
            recipients.append(user)
    return recipients

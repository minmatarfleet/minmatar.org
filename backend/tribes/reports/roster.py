"""Roster resolution for tribe group reports."""

from eveonline.models import EveCharacter

from tribes.models import TribeGroupMembership, TribeGroupMembershipCharacter


def roster_user_ids(tribe_group) -> set[int]:
    """User IDs with active membership in this tribe group."""
    return set(
        TribeGroupMembership.objects.filter(
            tribe_group=tribe_group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        ).values_list("user_id", flat=True)
    )


def roster_character_pks(tribe_group) -> set[int]:
    """EveCharacter Django PKs committed to active memberships."""
    membership_ids = TribeGroupMembership.objects.filter(
        tribe_group=tribe_group,
        status=TribeGroupMembership.STATUS_ACTIVE,
    ).values_list("id", flat=True)
    return set(
        TribeGroupMembershipCharacter.objects.filter(
            membership_id__in=membership_ids
        ).values_list("character_id", flat=True)
    )


def roster_character_eve_ids(tribe_group) -> set[int]:
    """EVE character IDs (bare int) for roster characters."""
    pks = roster_character_pks(tribe_group)
    if not pks:
        return set()
    return set(
        EveCharacter.objects.filter(pk__in=pks).values_list(
            "character_id", flat=True
        )
    )

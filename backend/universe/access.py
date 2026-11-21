"""Who can see and manage what in the Universe section.

Structure visibility is strict and checked here, never in the page:

- Superusers see every structure.
- Alliance: every member of the alliance.
- Corporation: every member of the owning corporation.
- Private: directors and station managers of the owning corporation.

Every check runs over all of the user's characters, so an alt with the role
counts. A station manager sees their own corporation's private structures,
not a sibling corporation's. ``visible_structures`` and
``can_see_structure`` answer the same question, one as a queryset and one
for a row; the tests hold them to the same table.
"""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.db.models import Q, QuerySet

from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveCharacter, EveCorporation
from groups.helpers.feature_access import can_use_feature, user_affiliation
from structures.models import EveStructure

ALLIANCE_AFFILIATION = "Alliance"


def _signed_in(user) -> bool:
    return (
        user is not None
        and not isinstance(user, AnonymousUser)
        and getattr(user, "is_authenticated", False)
    )


def is_alliance_member(user) -> bool:
    if not _signed_in(user):
        return False
    affiliation = user_affiliation(user)
    return bool(affiliation and affiliation.name == ALLIANCE_AFFILIATION)


def member_corporation_ids(user) -> set[int]:
    """ESI corporation ids of every character the user has."""
    if not _signed_in(user):
        return set()
    return set(
        EveCharacter.objects.filter(
            user=user, corporation_id__isnull=False
        ).values_list("corporation_id", flat=True)
    )


def managed_corporation_ids(user) -> set[int]:
    """Corporations where one of the user's characters is a director or
    station manager (ESI Director and Station_Manager roles)."""
    if not _signed_in(user):
        return set()
    return set(
        EveCorporation.objects.filter(
            Q(directors__user=user) | Q(stewards__user=user)
        ).values_list("corporation_id", flat=True)
    )


def visible_structures(user, queryset: QuerySet | None = None) -> QuerySet:
    queryset = EveStructure.objects.all() if queryset is None else queryset
    if not _signed_in(user):
        return queryset.none()
    if user.is_superuser:
        return queryset
    rule = Q(pk__in=[])
    if is_alliance_member(user):
        rule |= Q(visibility=EveStructure.VISIBILITY_ALLIANCE)
    members = member_corporation_ids(user)
    if members:
        rule |= Q(
            visibility=EveStructure.VISIBILITY_CORPORATION,
            corporation__corporation_id__in=members,
        )
    managed = managed_corporation_ids(user)
    if managed:
        rule |= Q(corporation__corporation_id__in=managed)
    return queryset.filter(rule)


def can_see_structure(user, structure: EveStructure) -> bool:
    if not _signed_in(user):
        return False
    if user.is_superuser:
        return True
    owner = (
        structure.corporation.corporation_id
        if structure.corporation_id
        else None
    )
    if owner is not None and owner in managed_corporation_ids(user):
        return True
    if structure.visibility == EveStructure.VISIBILITY_ALLIANCE:
        return is_alliance_member(user)
    if structure.visibility == EveStructure.VISIBILITY_CORPORATION:
        return owner is not None and owner in member_corporation_ids(user)
    return False


def can_change_visibility(user, structure: EveStructure) -> bool:
    """ESI rows only: reported structures are always alliance-wide."""
    if structure.source != EveStructure.SOURCE_ESI:
        return False
    if not _signed_in(user):
        return False
    if user.is_superuser:
        return True
    return bool(
        structure.corporation_id
        and structure.corporation.corporation_id
        in managed_corporation_ids(user)
    )


def manages_alliance_structures(user) -> bool:
    """A director or station manager of one of the alliance's corporations."""
    if not _signed_in(user):
        return False
    return EveCorporation.objects.filter(
        Q(directors__user=user) | Q(stewards__user=user),
        alliance__alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
    ).exists()


def can_see_moon_contents(user) -> bool:
    """Ores, scans and ISK a month: Strategic FCs, the alliance's structure
    managers and superusers. Everyone else sees only which moons exist."""
    if not _signed_in(user):
        return False
    if user.is_superuser:
        return True
    if can_use_feature(user, "fleets.manage_any"):
        return True
    return manages_alliance_structures(user)

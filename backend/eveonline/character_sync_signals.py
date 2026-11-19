"""Bring character sync sections forward when something makes them urgent.

- An industry assignment: the assignee's (and their alts') industry jobs.
- A new industry order: the owner's contracts.
- A pilot joining a fleet: their killmails and mining (15 minutes later).
- A pilot back from leave: every section.

Each only moves ``next_due_at`` earlier (``character_sync.mark_due``); the
interval itself is worked out when the row is next stamped.
"""

from __future__ import annotations

import logging

from django.db.models import signals
from django.dispatch import receiver
from django.utils import timezone

from eveonline import character_sync
from eveonline.models import EveCharacter
from fleets.models import EveFleetInstanceMember
from groups.models import UserCommunityStatus
from industry.models import IndustryOrder, IndustryOrderItemAssignment

logger = logging.getLogger(__name__)


def _user_character_pks(character: EveCharacter | None) -> list[int]:
    if character is None:
        return []
    if character.user_id:
        return list(
            EveCharacter.objects.filter(user_id=character.user_id).values_list(
                "pk", flat=True
            )
        )
    return [character.pk]


@receiver(
    signals.post_save,
    sender=IndustryOrderItemAssignment,
    dispatch_uid="character_sync_assignment_created",
)
def assignment_created(sender, instance, created, **kwargs):
    if not created:
        return
    character_sync.mark_due(
        _user_character_pks(instance.character),
        [character_sync.INDUSTRY_JOBS],
    )


@receiver(
    signals.post_save,
    sender=IndustryOrder,
    dispatch_uid="character_sync_order_created",
)
def order_created(sender, instance, created, **kwargs):
    if not created or instance.character_id is None:
        return
    character_sync.mark_due(
        [instance.character_id], [character_sync.CONTRACTS]
    )


@receiver(
    signals.post_save,
    sender=EveFleetInstanceMember,
    dispatch_uid="character_sync_fleet_member_joined",
)
def fleet_member_joined(sender, instance, created, **kwargs):
    if not created:
        return
    pks = list(
        EveCharacter.objects.filter(
            character_id=instance.character_id
        ).values_list("pk", flat=True)
    )
    character_sync.mark_due(
        pks,
        [character_sync.KILLMAILS, character_sync.MINING],
        when=timezone.now() + character_sync.FLEET_INTERVAL,
    )


@receiver(
    signals.pre_save,
    sender=UserCommunityStatus,
    dispatch_uid="character_sync_status_before",
)
def remember_previous_status(sender, instance, **kwargs):
    previous = None
    if instance.pk:
        previous = (
            UserCommunityStatus.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )
    instance.character_sync_previous_status = previous


@receiver(
    signals.post_save,
    sender=UserCommunityStatus,
    dispatch_uid="character_sync_back_from_leave",
)
def back_from_leave(sender, instance, **kwargs):
    previous = getattr(instance, "character_sync_previous_status", None)
    if (
        previous != UserCommunityStatus.STATUS_ON_LEAVE
        or instance.status == UserCommunityStatus.STATUS_ON_LEAVE
    ):
        return
    pks = list(
        EveCharacter.objects.filter(user_id=instance.user_id).values_list(
            "pk", flat=True
        )
    )
    character_sync.mark_due(pks, character_sync.SECTIONS_BY_NAME.keys())

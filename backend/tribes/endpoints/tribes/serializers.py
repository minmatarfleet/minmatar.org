"""Shared tribe → API schema helpers."""

from tribes.endpoints.serialization import user_to_character_ref
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribe_discord.access import can_manage_tribe_discord
from tribes.helpers.chiefs import (
    ChiefResolver,
    has_pending_offer,
    user_is_executor,
)
from tribes.models import Tribe, TribeGroupMembership


def serialize_tribe(
    tribe: Tribe,
    *,
    request_user=None,
    resolver: ChiefResolver | None = None,
) -> TribeSchema:
    resolver = resolver or ChiefResolver()
    acting = resolver.for_tribe(tribe)
    can_appoint_chief = False
    has_volunteered = False
    if acting.is_interim and request_user is not None:
        can_appoint_chief = user_is_executor(request_user, resolver)
        has_volunteered = has_pending_offer(request_user, tribe, None)
    active_groups = tribe.groups.filter(is_active=True)
    total_members = (
        TribeGroupMembership.objects.filter(
            tribe_group__tribe=tribe,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        .values("user")
        .distinct()
        .count()
    )
    return TribeSchema(
        id=tribe.pk,
        name=tribe.name,
        slug=tribe.slug,
        description=tribe.description,
        content=tribe.content,
        image_url=tribe.image_url,
        banner_url=tribe.banner_url,
        discord_channel_id=tribe.discord_channel_id,
        chief=user_to_character_ref(tribe.chief) if tribe.chief else None,
        acting_chief=(
            user_to_character_ref(acting.user) if acting.user else None
        ),
        chief_is_interim=acting.is_interim,
        can_appoint_chief=can_appoint_chief,
        can_set_chief=bool(getattr(request_user, "is_superuser", False)),
        can_manage_discord=can_manage_tribe_discord(request_user, tribe),
        has_volunteered=has_volunteered,
        is_active=tribe.is_active,
        group_count=active_groups.count(),
        total_member_count=total_members,
    )

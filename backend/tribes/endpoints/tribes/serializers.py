"""Shared tribe → API schema helpers."""

from tribes.endpoints.serialization import user_to_character_ref
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.models import Tribe, TribeGroupMembership


def serialize_tribe(tribe: Tribe) -> TribeSchema:
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
        is_active=tribe.is_active,
        group_count=active_groups.count(),
        total_member_count=total_members,
    )

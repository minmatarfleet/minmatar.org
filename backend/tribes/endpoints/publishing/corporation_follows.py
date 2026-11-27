"""The group's corporation follows, for its managers' settings."""

from eveonline.helpers.characters.identity import (
    primary_characters_for_users,
)
from tribes.endpoints.publishing.schemas import GroupCorporationFollowSchema
from tribes.models import TribeGroupCorporationFollow


def serialize_corporation_follows(group) -> list[GroupCorporationFollowSchema]:
    follows = list(
        TribeGroupCorporationFollow.objects.filter(tribe_group=group)
        .select_related("corporation")
        .order_by("corporation__name")
    )
    mains = primary_characters_for_users(
        follow.decided_by_id for follow in follows if follow.decided_by_id
    )
    rows = []
    for follow in follows:
        main = mains.get(follow.decided_by_id)
        rows.append(
            GroupCorporationFollowSchema(
                follow_id=follow.id,
                corporation_id=follow.corporation.corporation_id,
                corporation_name=follow.corporation.name,
                channel_name=follow.channel_name,
                status=follow.status,
                requested_at=follow.created_at,
                decided_by_name=main.character_name if main else None,
                decided_at=follow.decided_at,
                last_delivery_ok=follow.last_delivery_ok,
            )
        )
    return rows

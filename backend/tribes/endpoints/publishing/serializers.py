"""Build the publishing settings response for a tribe group."""

from eveonline.helpers.characters.identity import (
    primary_characters_for_users,
)
from tribes.endpoints.publishing.schemas import (
    PublisherSchema,
    TribeGroupPublishingSchema,
)
from tribes.helpers.discord_channels import channel_name
from tribes.helpers.publishing import group_role_name
from tribes.models import TribeGroup


def _publishers(users) -> list[PublisherSchema]:
    users = list(users)
    mains = primary_characters_for_users(user.pk for user in users)
    rows = []
    for user in users:
        main = mains.get(user.pk)
        if main is None:
            continue
        rows.append(
            PublisherSchema(
                character_id=main.character_id,
                character_name=main.character_name,
            )
        )
    return sorted(rows, key=lambda row: row.character_name.lower())


def serialize_publishing(group: TribeGroup) -> TribeGroupPublishingSchema:
    effective_id = group.effective_discord_channel_id
    return TribeGroupPublishingSchema(
        group_id=group.pk,
        post_policy=group.post_policy,
        fleet_policy=group.fleet_policy,
        event_policy=group.event_policy,
        post_publishers=_publishers(group.post_publishers.all()),
        fleet_publishers=_publishers(group.fleet_publishers.all()),
        event_publishers=_publishers(group.event_publishers.all()),
        allow_alliance_posts=group.allow_alliance_posts,
        allow_open_fleets=group.allow_open_fleets,
        discord_channel_id=group.discord_channel_id,
        effective_discord_channel_id=effective_id,
        effective_discord_channel_name=channel_name(effective_id),
        discord_role_name=group_role_name(group),
    )

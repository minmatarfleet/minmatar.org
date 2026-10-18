"""The fleet start ping: where it goes and what it says.

``EveFleet.notify_discord`` sends it and ``POST /fleets/ping-preview``
shows it, so the preview is always the message the bot will post.

An alliance fleet pings its audience's channel with @everyone. A tribe
group fleet pings the group's channel (or its tribe's) with the group's
role, never @everyone, and has no ping when there is no channel.
"""

from __future__ import annotations

from dataclasses import dataclass

from fleets.notifications import get_fleet_discord_notification

ALLIANCE_PING_CONTENT = "@everyone"


@dataclass
class StartPing:
    channel_id: int | None
    channel_name: str | None
    payload: dict


def build_start_ping(
    *,
    fleet_id: int,
    fleet_type_label: str,
    location_name: str | None,
    audience,
    host_group,
    fc_character,
    description: str,
    doctrine=None,
) -> StartPing | None:
    """The start ping for these fleet details; None with no destination.

    ``channel_id`` is None when the destination has no channel, in which
    case nothing is sent.
    """
    if host_group is not None:
        # pylint: disable=import-outside-toplevel
        from tribes.helpers.publishing import group_role_mention

        channel_id = host_group.effective_discord_channel_id
        channel_name = None
        content = group_role_mention(host_group)
        audience_label = host_group.name
    elif audience is not None:
        channel_id = audience.discord_channel_id
        channel_name = audience.discord_channel_name
        content = ALLIANCE_PING_CONTENT
        audience_label = audience.name
    else:
        return None

    payload = get_fleet_discord_notification(
        fleet_id=fleet_id,
        fleet_type=fleet_type_label,
        fleet_location=location_name or "Ask FC",
        fleet_audience=audience_label,
        fleet_commander_name=(
            fc_character.character_name if fc_character else ""
        ),
        fleet_commander_id=fc_character.character_id if fc_character else 0,
        fleet_description=description,
        fleet_voice_channel=None,
        fleet_voice_channel_link=None,
        fleet_doctrine=doctrine,
        content=content,
    )
    return StartPing(
        channel_id=channel_id, channel_name=channel_name, payload=payload
    )

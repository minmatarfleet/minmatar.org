"""Tribe group events: the Discord scheduled event and its announcement.

The site keeps the event; Discord shows it and collects "Interested".
Everything sent to Discord is built here so the announcement preview is
the message the bot posts. See docs/tribes/tribe-publishing.md (Events).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.conf import settings

from tribes.helpers.discord_channels import find_channel
from tribes.helpers.publishing import group_role_mention
from tribes.models import TribeEvent

# Discord guild scheduled event constants.
PRIVACY_GUILD_ONLY = 2
ENTITY_STAGE = 1
ENTITY_VOICE = 2
ENTITY_EXTERNAL = 3
STATUS_CANCELED = 4
FREQUENCY_MONTHLY = 1
FREQUENCY_WEEKLY = 2

DESCRIPTION_LIMIT = 1000
WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}
# How long an event with no end time counts as still happening.
DEFAULT_LENGTH = timedelta(hours=2)


def discord_event_url(discord_event_id: int | None) -> str | None:
    if not discord_event_id:
        return None
    return (
        f"https://discord.com/events/{settings.DISCORD_GUILD_ID}/"
        f"{discord_event_id}"
    )


def nth_weekday(moment: datetime) -> int:
    """Which occurrence of its weekday in the month (1-5)."""
    return (moment.day - 1) // 7 + 1


def recurrence_rule(event: TribeEvent) -> dict | None:
    """Discord's recurrence_rule; monthly repeats on the nth weekday."""
    if event.recurrence == TribeEvent.RECURRENCE_NONE:
        return None
    rule = {"start": event.starts_at.isoformat(), "interval": 1}
    weekday = event.starts_at.weekday()  # Discord: 0 = Monday, as Python
    if event.recurrence == TribeEvent.RECURRENCE_WEEKLY:
        rule.update(frequency=FREQUENCY_WEEKLY, by_weekday=[weekday])
    else:
        rule.update(
            frequency=FREQUENCY_MONTHLY,
            by_n_weekday=[{"n": nth_weekday(event.starts_at), "day": weekday}],
        )
    return rule


def recurrence_label(event: TribeEvent) -> str:
    weekday = WEEKDAYS[event.starts_at.weekday()]
    if event.recurrence == TribeEvent.RECURRENCE_WEEKLY:
        return f"Every {weekday}"
    if event.recurrence == TribeEvent.RECURRENCE_MONTHLY:
        nth = ORDINALS[nth_weekday(event.starts_at)]
        return f"Every {nth} {weekday} of the month"
    return "Does not repeat"


def where_label(event: TribeEvent) -> str:
    if event.where_kind == TribeEvent.WHERE_PLACE:
        return event.location
    return event.voice_channel_name or "Voice channel"


def entity_type(event: TribeEvent) -> int:
    if event.where_kind == TribeEvent.WHERE_PLACE:
        return ENTITY_EXTERNAL
    channel = find_channel(event.voice_channel_id)
    if channel and channel["type"] == "stage":
        return ENTITY_STAGE
    return ENTITY_VOICE


def event_description(event: TribeEvent) -> str:
    text = f"Hosted by {event.tribe_group.name}."
    if event.description:
        text += f"\n\n{event.description}"
    return text[:DESCRIPTION_LIMIT]


def discord_event_payload(event: TribeEvent) -> dict:
    """The create/modify body for the guild scheduled event."""
    payload = {
        "name": event.title[:100],
        "description": event_description(event),
        "privacy_level": PRIVACY_GUILD_ONLY,
        "scheduled_start_time": event.starts_at.isoformat(),
        "entity_type": entity_type(event),
        "recurrence_rule": recurrence_rule(event),
    }
    if event.ends_at:
        payload["scheduled_end_time"] = event.ends_at.isoformat()
    if payload["entity_type"] == ENTITY_EXTERNAL:
        payload["channel_id"] = None
        payload["entity_metadata"] = {"location": event.location[:100]}
    else:
        payload["channel_id"] = str(event.voice_channel_id)
        payload["entity_metadata"] = None
    return payload


def announcement_content(event: TribeEvent, event_url: str) -> str:
    """Role mention, one line about the event, then the event link."""
    mention = group_role_mention(event.tribe_group)
    prefix = f"{mention} " if mention else ""
    when = f"<t:{int(event.starts_at.timestamp())}:F>"
    repeat = (
        f" ({recurrence_label(event).lower()})"
        if event.recurrence != TribeEvent.RECURRENCE_NONE
        else ""
    )
    return (
        f"{prefix}**{event.title}** · {when}{repeat} · {where_label(event)}"
        f"\n{event_url}"
    )


def preview_event_url() -> str:
    """Stands in for the link before Discord has created the event."""
    return f"https://discord.com/events/{settings.DISCORD_GUILD_ID}/new"


def event_ends(event: TribeEvent) -> datetime:
    return event.ends_at or event.starts_at + DEFAULT_LENGTH

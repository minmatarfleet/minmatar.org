"""Check a tribe event's fields before it is saved."""

from django.utils import timezone

from tribes.helpers.discord_channels import channels_of_kind, find_channel
from tribes.models import TribeEvent


def apply_event_fields(event: TribeEvent, fields: dict) -> str | None:
    """Set ``fields`` on the event and check the result.

    Returns an error message, or None when the event is valid. Enums may
    come in as Enum members or plain strings.
    """
    for name, value in fields.items():
        setattr(event, name, getattr(value, "value", value))
    if event.where_kind == TribeEvent.WHERE_VOICE:
        event.location = ""
    else:
        event.voice_channel_id = None
        event.voice_channel_name = ""
    return _event_error(event)


def _event_error(event: TribeEvent) -> str | None:
    if not (event.title or "").strip():
        return "An event needs a title."
    if event.starts_at <= timezone.now():
        return "An event must start in the future."
    if event.ends_at and event.ends_at <= event.starts_at:
        return "An event must end after it starts."
    if event.where_kind == TribeEvent.WHERE_PLACE:
        if event.members_only:
            # Discord shows a location event to the whole server.
            return "A members-only event must be in a voice channel."
        if not (event.location or "").strip():
            return "Say where the event is."
        if not event.ends_at:
            return "An event somewhere other than voice needs an end time."
        return None
    return _voice_error(event)


def _voice_error(event: TribeEvent) -> str | None:
    if not event.voice_channel_id:
        return "Pick a voice channel."
    voice = channels_of_kind("voice")
    channel = find_channel(event.voice_channel_id)
    if voice and (channel is None or channel not in voice):
        return f"{event.voice_channel_id} is not a voice channel."
    if channel:
        event.voice_channel_name = channel["name"]
    return None

"""Serialize tribe events."""

from tribes.endpoints.events.schemas import TribeEventSchema
from tribes.endpoints.serialization import user_to_character_ref
from tribes.helpers.events import (
    discord_event_url,
    recurrence_label,
    where_label,
)
from tribes.helpers.permissions import user_can_manage_group
from tribes.helpers.publishing import host_group_ref
from tribes.models import TribeEvent


def can_manage_event(user, event: TribeEvent) -> bool:
    """The event's creator, or anyone who can manage its group."""
    if not getattr(user, "is_authenticated", False) or not user.pk:
        return False
    if event.created_by_id and event.created_by_id == user.pk:
        return True
    return user_can_manage_group(user, event.tribe_group)


def serialize_event(
    event: TribeEvent, user=None, manages_group: bool | None = None
) -> TribeEventSchema:
    """``manages_group``: whether the viewer manages the event's group,
    when a list already knows."""
    if manages_group is None:
        can_manage = can_manage_event(user, event)
    else:
        can_manage = manages_group or bool(
            user is not None
            and event.created_by_id
            and event.created_by_id == getattr(user, "pk", None)
        )
    return TribeEventSchema(
        id=event.pk,
        tribe_group=host_group_ref(event.tribe_group),
        created_by=(
            user_to_character_ref(event.created_by)
            if event.created_by_id
            else None
        ),
        title=event.title,
        description=event.description,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        recurrence=event.recurrence,
        recurrence_label=recurrence_label(event),
        where_kind=event.where_kind,
        voice_channel_id=(
            str(event.voice_channel_id) if event.voice_channel_id else None
        ),
        voice_channel_name=event.voice_channel_name,
        location=event.location,
        where_label=where_label(event),
        members_only=event.members_only,
        announce=event.announce,
        discord_event_id=(
            str(event.discord_event_id) if event.discord_event_id else None
        ),
        discord_event_url=discord_event_url(event.discord_event_id),
        interested_count=event.interested_count,
        status=event.status,
        cancelled_at=event.cancelled_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
        can_manage=can_manage,
    )

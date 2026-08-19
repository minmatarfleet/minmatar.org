"""Shared Discord-button actions for NPSI events."""

from __future__ import annotations

import logging

from django.contrib.auth.models import User

from discord.client import DiscordClient
from discord.models import DiscordUser
from groups.helpers.feature_access import can_use_feature
from fleets.endpoints.helpers import send_discord_pre_ping
from fleets.endpoints.schemas import CreateEveFleetRequest
from fleets.helpers.npsi_discord import posted_dm_payload
from fleets.helpers.npsi_ingest import resolve_fc_user
from fleets.helpers.schedule_fleet import create_scheduled_fleet
from fleets.models import NpsiExternalEvent

logger = logging.getLogger(__name__)


class NpsiActionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def actor_from_discord_id(discord_user_id: int) -> User:
    discord_user = (
        DiscordUser.objects.filter(id=discord_user_id)
        .select_related("user")
        .first()
    )
    if discord_user is None:
        raise NpsiActionError("Unknown Discord user.", status_code=403)
    return discord_user.user


def authorize_npsi_actor(
    *, requester: User, actor: User, fc_user: User
) -> None:
    if requester.pk != actor.pk and not (
        requester.is_staff or requester.is_superuser
    ):
        raise NpsiActionError("Not authorized.", status_code=403)
    if actor.pk != fc_user.pk and not (actor.is_staff or actor.is_superuser):
        raise NpsiActionError(
            "Only the FC (or staff) can post this event.",
            status_code=403,
        )


def fc_user_for_event(event: NpsiExternalEvent) -> User:
    name = event.character_name or event.source.fc_character_name
    fc_user = resolve_fc_user(name)
    if fc_user is None:
        raise NpsiActionError(
            "FC character is not linked to a site user.",
            status_code=400,
        )
    return fc_user


def post_event_to_schedule(event: NpsiExternalEvent) -> NpsiExternalEvent:
    if event.status == NpsiExternalEvent.Status.CREATED and event.eve_fleet_id:
        return event

    source = event.source
    if source.default_audience_id is None:
        raise NpsiActionError("Source has no default audience.")

    fc_user = fc_user_for_event(event)
    if not can_use_feature(fc_user, "fleets.create"):
        raise NpsiActionError("FC cannot create fleets.", status_code=403)

    location_id = None
    if source.default_location_id:
        location_id = source.default_location.location_id

    objective = (event.summary or "")[:200]
    payload = CreateEveFleetRequest(
        type=source.default_type,
        description=event.description or event.summary,
        objective=objective,
        start_time=event.start_time,
        audience_id=source.default_audience_id,
        location_id=location_id,
        immediate_ping=False,
    )
    result = create_scheduled_fleet(user=fc_user, payload=payload)
    if isinstance(result, tuple):
        _, body = result
        detail = body.get("detail") if isinstance(body, dict) else str(body)
        raise NpsiActionError(str(detail), status_code=400)

    event.eve_fleet = result
    event.status = NpsiExternalEvent.Status.CREATED
    event.skip_reason = ""
    event.save(
        update_fields=["eve_fleet", "status", "skip_reason", "updated_at"]
    )
    _update_notify_message(event)
    return event


def _update_notify_message(event: NpsiExternalEvent) -> None:
    if not event.discord_channel_id or not event.discord_message_id:
        return
    try:
        DiscordClient().update_message(
            event.discord_channel_id,
            event.discord_message_id,
            payload=posted_dm_payload(event),
        )
    except Exception:
        logger.warning(
            "Could not update NPSI notify DM event=%s",
            event.id,
            exc_info=True,
        )


def preping_event(event: NpsiExternalEvent) -> None:
    if event.eve_fleet is None:
        raise NpsiActionError("Post the event to the schedule first.")
    sent = send_discord_pre_ping(event.eve_fleet)
    if not sent:
        raise NpsiActionError("Could not send pre-ping.", status_code=500)


def track_event(event: NpsiExternalEvent) -> None:
    fleet = event.eve_fleet
    if fleet is None:
        raise NpsiActionError("Post the event to the schedule first.")
    try:
        fleet.start(None)
    except Exception as exc:
        message = str(exc)
        if "not in a fleet" in message:
            raise NpsiActionError("Not currently in a fleet.") from exc
        if "not the fleet commander" in message:
            raise NpsiActionError(
                "Must be the fleet commander of your in-game fleet."
            ) from exc
        raise NpsiActionError(f"Error starting fleet: {exc}") from exc

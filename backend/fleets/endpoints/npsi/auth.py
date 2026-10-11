"""Shared auth for NPSI Discord button endpoints."""

from django.http import HttpRequest

from fleets.helpers.npsi_actions import (
    NpsiActionError,
    actor_from_discord_id,
    authorize_npsi_actor,
    fc_user_for_event,
)
from fleets.models import NpsiExternalEvent


def load_event(event_id: int) -> NpsiExternalEvent:
    event = (
        NpsiExternalEvent.objects.select_related(
            "source",
            "source__default_audience",
            "source__default_location",
            "eve_fleet",
        )
        .filter(id=event_id)
        .first()
    )
    if event is None:
        raise NpsiActionError("Event not found.", status_code=404)
    return event


def authorize_request(
    request: HttpRequest, event: NpsiExternalEvent, discord_user_id: int
):
    actor = actor_from_discord_id(discord_user_id)
    fc_user = fc_user_for_event(event)
    authorize_npsi_actor(requester=request.user, actor=actor, fc_user=fc_user)
    return actor

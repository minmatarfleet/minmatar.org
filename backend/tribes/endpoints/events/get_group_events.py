"""GET "/groups/{group_id}/events" (registered in __init__ with POST)."""

from typing import List

from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthOptional
from tribes.endpoints.events.schemas import TribeEventSchema
from tribes.endpoints.events.serializers import serialize_event
from tribes.helpers.event_sync import upcoming_events_q
from tribes.helpers.publishing import can_manage, can_view_group_items
from tribes.models import TribeEvent, TribeGroup

PATH = "/groups/{group_id}/events"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "A group's upcoming events.",
    "description": (
        "Scheduled events that aren't over, and ones cancelled in the last "
        "24 hours. Members-only events are left out for viewers outside "
        "the group (their creator still sees them)."
    ),
    "response": {200: List[TribeEventSchema], 404: ErrorResponse},
    "auth": AuthOptional(),
}


def get_group_events(request, group_id: int):
    group = (
        TribeGroup.objects.filter(pk=group_id).select_related("tribe").first()
    )
    if group is None:
        return 404, {"detail": "TribeGroup not found."}
    user = request.user
    events = (
        TribeEvent.objects.filter(upcoming_events_q(timezone.now()))
        .filter(tribe_group=group)
        .select_related(
            "tribe_group__tribe", "created_by__eveplayer__primary_character"
        )
        .order_by("starts_at")
    )
    if not can_view_group_items(user, group):
        events = [
            event
            for event in events
            if not event.members_only
            or (event.created_by_id and event.created_by_id == user.pk)
        ]
    manages = can_manage(user, group)
    return 200, [
        serialize_event(event, user, manages_group=manages) for event in events
    ]

"""POST "/groups/{group_id}/events" (registered in __init__ with GET)."""

from django.db import transaction

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.events.schemas import TribeEventCreate, TribeEventSchema
from tribes.endpoints.events.serializers import serialize_event
from tribes.endpoints.events.validation import apply_event_fields
from tribes.helpers.event_sync import queue_event_sync
from tribes.helpers.publishing import KIND_EVENT, can_publish
from tribes.models import TribeEvent, TribeGroup

PATH = "/groups/{group_id}/events"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Create a group event (and its Discord scheduled event).",
    "description": (
        "Needs the group's event publishing right. The Discord event and "
        "the announcement are created by a worker after the save."
    ),
    "response": {
        200: TribeEventSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
}


def load_publishable_group(user, group_id: int):
    """The group, or a 404/403 error tuple."""
    group = (
        TribeGroup.objects.filter(pk=group_id)
        .select_related("tribe", "group__discord_group")
        .first()
    )
    if group is None:
        return 404, {"detail": "TribeGroup not found."}
    if not can_publish(user, group, KIND_EVENT):
        return 403, {"detail": f"You can't create events for {group.name}."}
    return group


def post_group_event(request, group_id: int, payload: TribeEventCreate):
    # Imported here: tribes.tasks imports the routers' helpers.
    from tribes.tasks import (  # pylint: disable=import-outside-toplevel
        create_tribe_discord_event,
    )

    group = load_publishable_group(request.user, group_id)
    if isinstance(group, tuple):
        return group
    event = TribeEvent(tribe_group=group, created_by=request.user)
    error = apply_event_fields(event, payload.model_dump())
    if error:
        return 400, {"detail": error}
    with transaction.atomic():
        event.save()
        queue_event_sync(create_tribe_discord_event, event.pk)
    return 200, serialize_event(event, request.user)

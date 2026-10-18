"""PATCH "/events/{event_id}" - edit a group event."""

from django.db import transaction
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.events.schemas import TribeEventPatch, TribeEventSchema
from tribes.endpoints.events.serializers import (
    can_manage_event,
    serialize_event,
)
from tribes.endpoints.events.validation import apply_event_fields
from tribes.helpers.event_sync import queue_event_sync
from tribes.models import TribeEvent

PATH = "/events/{event_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Edit a group event; the Discord event follows.",
    "description": "The event's creator or a manager of its group.",
    "response": {
        200: TribeEventSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Events"])


def load_managed_event(user, event_id: int):
    """The event, or a 404/403 error tuple."""
    event = (
        TribeEvent.objects.filter(pk=event_id)
        .select_related("tribe_group__tribe", "tribe_group__group")
        .first()
    )
    if event is None:
        return 404, {"detail": "Event not found."}
    if not can_manage_event(user, event):
        return 403, {"detail": "Only the event's creator or group managers."}
    return event


def patch_event(request, event_id: int, payload: TribeEventPatch):
    from tribes.tasks import (  # pylint: disable=import-outside-toplevel
        update_tribe_discord_event,
    )

    event = load_managed_event(request.user, event_id)
    if isinstance(event, tuple):
        return event
    if event.status != TribeEvent.STATUS_SCHEDULED:
        return 400, {"detail": f"The event is {event.status}."}
    fields = payload.model_dump(exclude_unset=True)
    # Only ends_at and voice_channel_id may be cleared with null.
    fields = {
        name: value
        for name, value in fields.items()
        if value is not None or name in ("ends_at", "voice_channel_id")
    }
    error = apply_event_fields(event, fields)
    if error:
        return 400, {"detail": error}
    with transaction.atomic():
        event.save()
        queue_event_sync(update_tribe_discord_event, event.pk)
    return 200, serialize_event(event, request.user)


router.patch(PATH, **ROUTE_SPEC)(patch_event)

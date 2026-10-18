"""POST "/events/{event_id}/cancel" - cancel a group event."""

from django.db import transaction
from django.utils import timezone
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.events.patch_event import load_managed_event
from tribes.endpoints.events.schemas import TribeEventSchema
from tribes.endpoints.events.serializers import serialize_event
from tribes.helpers.event_sync import queue_event_sync
from tribes.models import TribeEvent

PATH = "/events/{event_id}/cancel"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Cancel a group event; the Discord event is cancelled too.",
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


def post_event_cancel(request, event_id: int):
    from tribes.tasks import (  # pylint: disable=import-outside-toplevel
        cancel_tribe_discord_event,
    )

    event = load_managed_event(request.user, event_id)
    if isinstance(event, tuple):
        return event
    if event.status != TribeEvent.STATUS_SCHEDULED:
        return 400, {"detail": f"The event is {event.status}."}
    event.status = TribeEvent.STATUS_CANCELLED
    event.cancelled_at = timezone.now()
    with transaction.atomic():
        event.save()
        queue_event_sync(cancel_tribe_discord_event, event.pk)
    return 200, serialize_event(event, request.user)


router.post(PATH, **ROUTE_SPEC)(post_event_cancel)

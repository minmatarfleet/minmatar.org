"""POST "/groups/{group_id}/events/announcement-preview"."""

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.events.post_group_event import load_publishable_group
from tribes.endpoints.events.schemas import (
    TribeEventAnnouncementPreview,
    TribeEventCreate,
    TribeEventPreviewSchema,
)
from tribes.endpoints.events.validation import apply_event_fields
from tribes.helpers.discord_channels import channel_name
from tribes.helpers.events import (
    announcement_content,
    preview_event_url,
    recurrence_label,
    where_label,
)
from tribes.models import TribeEvent

PATH = "/groups/{group_id}/events/announcement-preview"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "The announcement a new group event would post.",
    "description": (
        "Built by the same code as the real announcement. content is null "
        "when announce is off or the group has no channel; the event link "
        "is a placeholder until Discord creates the event."
    ),
    "response": {
        200: TribeEventAnnouncementPreview,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Events"])


def post_event_announcement_preview(
    request, group_id: int, payload: TribeEventCreate
):
    group = load_publishable_group(request.user, group_id)
    if isinstance(group, tuple):
        return group
    event = TribeEvent(tribe_group=group, created_by=request.user)
    error = apply_event_fields(event, payload.model_dump())
    if error:
        return 400, {"detail": error}
    channel_id = group.effective_discord_channel_id
    content = None
    if event.announce and channel_id:
        content = announcement_content(event, preview_event_url())
    return 200, TribeEventAnnouncementPreview(
        channel_name=channel_name(channel_id) if channel_id else None,
        content=content,
        event_preview=TribeEventPreviewSchema(
            title=event.title,
            starts_at=event.starts_at,
            where_label=where_label(event),
            recurrence_label=recurrence_label(event),
        ),
    )


router.post(PATH, **ROUTE_SPEC)(post_event_announcement_preview)

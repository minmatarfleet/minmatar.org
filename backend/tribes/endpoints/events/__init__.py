"""Tribe group event endpoints."""

from ninja import Router

from tribes.endpoints.events.get_group_events import (
    PATH as GROUP_EVENTS_PATH,
    ROUTE_SPEC as GET_GROUP_EVENTS_SPEC,
    get_group_events,
)
from tribes.endpoints.events.patch_event import router as patch_event_router
from tribes.endpoints.events.post_event_announcement_preview import (
    router as post_event_announcement_preview_router,
)
from tribes.endpoints.events.post_event_cancel import (
    router as post_event_cancel_router,
)
from tribes.endpoints.events.post_group_event import (
    ROUTE_SPEC as POST_GROUP_EVENT_SPEC,
    post_group_event,
)

router = Router(tags=["Tribes - Events"])
# GET and POST share a path, so they go on one Router (see memberships).
router.get(GROUP_EVENTS_PATH, **GET_GROUP_EVENTS_SPEC)(get_group_events)
router.post(GROUP_EVENTS_PATH, **POST_GROUP_EVENT_SPEC)(post_group_event)
router.add_router("", post_event_announcement_preview_router)
router.add_router("", patch_event_router)
router.add_router("", post_event_cancel_router)

__all__ = ["router"]

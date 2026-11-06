"""Chief volunteers: pilots offer to lead an open seat; the executor decides."""

from ninja import Router

# GET and POST share one path, so they register on this Router together.
from tribes.endpoints.chief_volunteers.post_appoint import (
    router as post_appoint_router,
)
from tribes.endpoints.chief_volunteers.post_decline import (
    router as post_decline_router,
)
from tribes.endpoints.chief_volunteers.post_discord_appoint import (
    router as post_discord_appoint_router,
)
from tribes.endpoints.chief_volunteers.post_discord_decline import (
    router as post_discord_decline_router,
)
from tribes.endpoints.chief_volunteers.seat_volunteers import (
    GET_ROUTE_SPEC,
    PATH as SEAT_PATH,
    POST_ROUTE_SPEC,
    get_chief_volunteers,
    post_chief_volunteer,
)

router = Router(tags=["Tribes - Chiefs"])

# "/chief-volunteers/..." before "/{tribe_id}/..." so it isn't a tribe id.
router.add_router("", post_appoint_router)
router.add_router("", post_decline_router)
router.add_router("", post_discord_appoint_router)
router.add_router("", post_discord_decline_router)
router.get(SEAT_PATH, **GET_ROUTE_SPEC)(get_chief_volunteers)
router.post(SEAT_PATH, **POST_ROUTE_SPEC)(post_chief_volunteer)

__all__ = ["router"]

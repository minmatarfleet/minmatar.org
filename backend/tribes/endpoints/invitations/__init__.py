"""Tribe group invitations: chiefs invite, pilots accept or decline."""

from ninja import Router

# GET and POST share one path, so they register on this Router together.
from tribes.endpoints.invitations.get_group_invitations import (
    PATH as GROUP_INVITATIONS_PATH,
    ROUTE_SPEC as GET_GROUP_INVITATIONS_SPEC,
    get_group_invitations,
)
from tribes.endpoints.invitations.post_group_invitations import (
    ROUTE_SPEC as POST_GROUP_INVITATIONS_SPEC,
    post_group_invitations,
)
from tribes.endpoints.invitations.get_invitation_candidates import (
    router as get_invitation_candidates_router,
)
from tribes.endpoints.invitations.delete_group_invitation import (
    router as delete_group_invitation_router,
)
from tribes.endpoints.invitations.get_my_invitations import (
    router as get_my_invitations_router,
)
from tribes.endpoints.invitations.post_invitation_accept import (
    router as post_invitation_accept_router,
)
from tribes.endpoints.invitations.post_invitation_decline import (
    router as post_invitation_decline_router,
)
from tribes.endpoints.invitations.post_invitation_discord_decline import (
    router as post_invitation_discord_decline_router,
)

router = Router(tags=["Tribes - Invitations"])

router.add_router("", get_my_invitations_router)
router.add_router("", post_invitation_accept_router)
router.add_router("", post_invitation_decline_router)
router.add_router("", post_invitation_discord_decline_router)

# "candidates" before {invitation_id} so it isn't captured as an id.
router.add_router("", get_invitation_candidates_router)
router.get(GROUP_INVITATIONS_PATH, **GET_GROUP_INVITATIONS_SPEC)(
    get_group_invitations
)
router.post(GROUP_INVITATIONS_PATH, **POST_GROUP_INVITATIONS_SPEC)(
    post_group_invitations
)
router.add_router("", delete_group_invitation_router)

__all__ = ["router"]

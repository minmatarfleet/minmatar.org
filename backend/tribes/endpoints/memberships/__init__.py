"""Membership lifecycle and committed-character endpoints."""

from ninja import Router

# GET and POST share the same URL path so they must be registered on the same
# Router instance — Django Ninja only allows one URL pattern per path, and it
# dispatches by method only when both are registered together.
from tribes.endpoints.memberships.post_membership import (
    PATH as MEMBERSHIPS_PATH,
    ROUTE_SPEC as POST_MEMBERSHIPS_SPEC,
    post_membership,
)
from tribes.endpoints.memberships.get_memberships import (
    ROUTE_SPEC as GET_MEMBERSHIPS_SPEC,
    get_memberships,
)
from tribes.endpoints.memberships.get_membership_characters_available import (
    PATH as CHARACTERS_AVAILABLE_PATH,
    ROUTE_SPEC as GET_CHARACTERS_AVAILABLE_SPEC,
    get_membership_characters_available,
)
from tribes.endpoints.memberships.post_membership_approve import (
    router as post_membership_approve_router,
)
from tribes.endpoints.memberships.post_membership_deny import (
    router as post_membership_deny_router,
)
from tribes.endpoints.memberships.delete_membership import (
    router as delete_membership_router,
)
from tribes.endpoints.memberships.get_membership_characters import (
    PATH as CHARACTERS_PATH,
    ROUTE_SPEC as GET_CHARACTERS_SPEC,
    get_membership_characters,
)
from tribes.endpoints.memberships.post_membership_character import (
    ROUTE_SPEC as POST_CHARACTERS_SPEC,
    post_membership_character,
)
from tribes.endpoints.memberships.delete_membership_character import (
    router as delete_membership_character_router,
)
from tribes.endpoints.memberships.get_membership_history import (
    router as get_membership_history_router,
)
from tribes.endpoints.memberships.get_membership_character_history import (
    router as get_membership_character_history_router,
)

router = Router(tags=["Tribes - Memberships"])

# Memberships collection — GET + POST share the same path.
router.get(MEMBERSHIPS_PATH, **GET_MEMBERSHIPS_SPEC)(get_memberships)
router.post(MEMBERSHIPS_PATH, **POST_MEMBERSHIPS_SPEC)(post_membership)

# Your characters and whether they qualify (owner only). Register before
# {membership_id} routes so "characters-available" is not captured as id.
router.get(CHARACTERS_AVAILABLE_PATH, **GET_CHARACTERS_AVAILABLE_SPEC)(
    get_membership_characters_available
)

router.add_router("", post_membership_approve_router)
router.add_router("", post_membership_deny_router)
router.add_router("", delete_membership_router)

# Characters sub-resource — GET + POST share the same path.
router.get(CHARACTERS_PATH, **GET_CHARACTERS_SPEC)(get_membership_characters)
router.post(CHARACTERS_PATH, **POST_CHARACTERS_SPEC)(post_membership_character)

router.add_router("", delete_membership_character_router)

# History sub-resources (read-only audit).
router.add_router("", get_membership_history_router)
router.add_router("", get_membership_character_history_router)

__all__ = ["router"]

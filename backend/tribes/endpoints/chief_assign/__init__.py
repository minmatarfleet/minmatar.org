"""Superusers swap a tribe or group chief from the site."""

from ninja import Router

from tribes.endpoints.chief_assign.get_candidates import (
    router as get_candidates_router,
)
from tribes.endpoints.chief_assign.put_chief import router as put_chief_router

router = Router(tags=["Tribes - Chiefs"])
# "/chief-candidates" before "/{tribe_id}/..." so it isn't a tribe id.
router.add_router("", get_candidates_router)
router.add_router("", put_chief_router)

__all__ = ["router"]

"""Surveys API router — composed from member and management sub-routers."""

from ninja import Router

from surveys.endpoints import get_exit_survey, post_exit_survey
from surveys.endpoints.manage import router as manage_router
from surveys.endpoints.member import router as member_router

router = Router(tags=["Surveys"])
router.add_router("", member_router)
router.add_router("", manage_router)

# Exit surveys (#3198): no login, the signed link is the key. GET and POST
# share a path, so both register on one router.
exit_router = Router(tags=["Surveys"])
for module in (get_exit_survey, post_exit_survey):
    handler = getattr(module, module.__name__.rsplit(".", 1)[1])
    getattr(exit_router, module.METHOD)(module.PATH, **module.ROUTE_SPEC)(
        handler
    )
router.add_router("", exit_router)

__all__ = ["router"]

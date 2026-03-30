"""Blueprints router: GET originals and GET copies with owner/primary character in SQL."""

from ninja import Router

from industry.endpoints.blueprints.get_blueprint import (
    METHOD as get_blueprint_method,
    PATH as get_blueprint_path,
    ROUTE_SPEC as get_blueprint_spec,
    get_blueprint,
)
from industry.endpoints.blueprints.get_blueprints import (
    router as get_blueprints_router,
)
from industry.endpoints.blueprints.get_blueprints_copies import (
    router as get_blueprints_copies_router,
)

router = Router(tags=["Industry - Blueprints"])
router.add_router("", get_blueprints_router)
getattr(router, get_blueprint_method)(
    get_blueprint_path,
    **get_blueprint_spec,
)(get_blueprint)
router.add_router("copies", get_blueprints_copies_router)

__all__ = ["router"]

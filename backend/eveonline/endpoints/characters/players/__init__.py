from ninja import Router

from eveonline.endpoints.characters.players.get_current import (
    get_current_player,
    ROUTE_SPEC as get_current_spec,
)
from eveonline.endpoints.characters.players.patch_current import (
    patch_current_player,
    ROUTE_SPEC as patch_current_spec,
)

router = Router(tags=["Players"])
router.get("current", **get_current_spec)(get_current_player)
router.patch("current", **patch_current_spec)(patch_current_player)

__all__ = ["router"]

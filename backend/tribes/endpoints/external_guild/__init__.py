"""External-guild seat endpoints for tribe Discord bindings."""

from ninja import Router

from tribes.endpoints.external_guild.get_external_guild_seat import (
    router as get_external_guild_seat_router,
)
from tribes.endpoints.external_guild.get_external_guild_join import (
    router as get_external_guild_join_router,
)
from tribes.endpoints.external_guild.get_external_guild_callback import (
    router as get_external_guild_callback_router,
)

router = Router(tags=["Tribes - External Guild"])
router.add_router("", get_external_guild_seat_router)
router.add_router("", get_external_guild_join_router)
router.add_router("", get_external_guild_callback_router)

__all__ = ["router"]

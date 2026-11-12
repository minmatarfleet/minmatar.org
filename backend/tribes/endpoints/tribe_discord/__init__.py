"""A tribe chief's Discord: one server, existing roles mapped to states.

GET, PUT and DELETE share a path, so they go on one router. Ninja answers
405 when a second router repeats a path with another method. The callback
is registered first so "/discord/bot/callback" is not read as a tribe id.
"""

from ninja import Router

from tribes.endpoints.tribe_discord import (
    delete_tribe_discord,
    get_tribe_discord,
    get_tribe_discord_bot_callback,
    get_tribe_discord_bot_connect,
    put_tribe_discord_roles,
)

router = Router(tags=["Tribes"])
router.add_router("", get_tribe_discord_bot_callback.router)
router.add_router("", get_tribe_discord_bot_connect.router)

discord_router = Router(tags=["Tribes"])
for endpoint in (
    get_tribe_discord,
    put_tribe_discord_roles,
    delete_tribe_discord,
):
    view = getattr(endpoint, endpoint.__name__.rsplit(".", 1)[-1])
    getattr(discord_router, endpoint.METHOD)(
        endpoint.PATH, **endpoint.ROUTE_SPEC
    )(view)
router.add_router("", discord_router)

__all__ = ["router"]

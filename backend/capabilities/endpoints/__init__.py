"""Training API: the Training tab on the account page."""

from ninja import Router

from capabilities.endpoints import (
    get_overview,
    get_character,
    patch_character,
    get_ships,
    post_goal,
    patch_goal,
    delete_goal,
    get_plan,
    get_accounts,
    put_account,
)

router = Router(tags=["Training"])

for module in (
    get_overview,
    get_character,
    patch_character,
    get_ships,
    post_goal,
    patch_goal,
    delete_goal,
    get_plan,
    get_accounts,
    put_account,
):
    view = getattr(module, module.__name__.rsplit(".", 1)[1])
    getattr(router, module.METHOD)(module.PATH, **module.ROUTE_SPEC)(view)

__all__ = ["router"]

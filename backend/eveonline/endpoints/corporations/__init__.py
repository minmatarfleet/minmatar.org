from ninja import Router

from eveonline.endpoints.corporations import (
    delete_corporation_discord,
    delete_corporation_discord_bot,
    get_corporation_discord,
    get_corporation_page_text,
    get_corporation_discord_bot_callback,
    get_corporation_discord_bot_connect,
    post_corporation_discord_bot_refresh,
    post_corporation_discord_check,
    post_corporation_discord_roles_refresh,
    put_corporation_discord,
    put_corporation_discord_roles,
    put_corporation_page_text,
)
from eveonline.endpoints.corporations.get_corp_member_details import (
    router as get_corp_member_details_router,
)
from eveonline.endpoints.corporations.get_corp_member_insights import (
    router as get_corp_member_insights_router,
)
from eveonline.endpoints.corporations.post_corp_member_promote import (
    router as post_corp_member_promote_router,
)
from eveonline.endpoints.corporations.get_corp_member_top import (
    router as get_corp_member_top_router,
)
from eveonline.endpoints.corporations.get_corporation_admin import (
    router as get_corporation_admin_router,
)
from eveonline.endpoints.corporations.get_corporation_applications_open import (
    router as get_corporation_applications_open_router,
)
from eveonline.endpoints.corporations.get_corporation_by_id import (
    router as get_corporation_by_id_router,
)
from eveonline.endpoints.corporations.get_corporation_by_slug import (
    router as get_corporation_by_slug_router,
)
from eveonline.endpoints.corporations.get_corporation_projects import (
    router as get_corporation_projects_router,
)
from eveonline.endpoints.corporations.get_corporation_info import (
    router as get_corporation_info_router,
)
from eveonline.endpoints.corporations.get_corporations import (
    router as get_corporations_router,
)
from eveonline.endpoints.corporations.get_managed_corp_ids import (
    router as get_managed_corp_ids_router,
)

router = Router(tags=["Corporations"])
router.add_router("", get_corporations_router)
router.add_router("", get_corporation_by_slug_router)
router.add_router("", get_corporation_by_id_router)
router.add_router("", get_corporation_info_router)
router.add_router("", get_corp_member_details_router)
router.add_router("", get_corp_member_insights_router)
router.add_router("", post_corp_member_promote_router)
router.add_router("", get_corp_member_top_router)
router.add_router("", get_corporation_admin_router)
router.add_router("", get_corporation_applications_open_router)
router.add_router("", get_managed_corp_ids_router)
router.add_router("", get_corporation_projects_router)

# The Discord endpoints share a path, so they go on one router: ninja answers
# 405 when a second router repeats a path with another method.
discord_router = Router(tags=["Corporations"])
for endpoint in (
    get_corporation_discord,
    put_corporation_discord,
    put_corporation_discord_roles,
    delete_corporation_discord,
    post_corporation_discord_check,
    get_corporation_discord_bot_connect,
    get_corporation_discord_bot_callback,
    delete_corporation_discord_bot,
    post_corporation_discord_bot_refresh,
    post_corporation_discord_roles_refresh,
):
    view = getattr(endpoint, endpoint.__name__.rsplit(".", 1)[-1])
    getattr(discord_router, endpoint.METHOD)(
        endpoint.PATH, **endpoint.ROUTE_SPEC
    )(view)
router.add_router("", discord_router)

# The page text endpoints share a path too.
page_text_router = Router(tags=["Corporations"])
for endpoint in (get_corporation_page_text, put_corporation_page_text):
    view = getattr(endpoint, endpoint.__name__.rsplit(".", 1)[-1])
    getattr(page_text_router, endpoint.METHOD)(
        endpoint.PATH, **endpoint.ROUTE_SPEC
    )(view)
router.add_router("", page_text_router)

__all__ = ["router"]

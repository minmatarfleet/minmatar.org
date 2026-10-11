from ninja import Router

from eveonline.endpoints.corporations.get_corp_member_details import (
    router as get_corp_member_details_router,
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
router.add_router("", get_corp_member_top_router)
router.add_router("", get_corporation_admin_router)
router.add_router("", get_corporation_applications_open_router)
router.add_router("", get_managed_corp_ids_router)

__all__ = ["router"]

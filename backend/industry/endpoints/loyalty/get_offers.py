"""GET /offers - public LP store offer catalog with economics."""

from typing import Optional

from django.db.models import Max
from ninja import Query

from industry.endpoints.loyalty.schemas import LoyaltyOffersListResponse
from industry.endpoints.loyalty.serialization import (
    offer_economics_row_response,
)
from industry.helpers.lp_store_offer_economics_rebuild import (
    rebuild_lp_store_offer_economics,
)
from industry.helpers.lp_store_offers_query import (
    DEFAULT_API_ORDERING,
    query_lp_store_offers,
)
from industry.models import IndustryLpStoreOffer, IndustryLpStoreOfferEconomics

PATH = "/offers"
METHOD = "get"
ROUTE_SPEC = {
    "summary": ("List tracked LP store offers with market economics (public)"),
    "response": {200: LoyaltyOffersListResponse},
}

# Optional page size for tools; UI loads the full filtered set.
MAX_LIMIT = 5000


def get_offers(
    request,
    currency: Optional[int] = None,
    exclude_tags: Optional[str] = None,
    exclude_supply_packages: Optional[str] = None,
    exclude_chips: Optional[str] = None,
    exclude_skins: Optional[str] = None,
    exclude_useless_offers: Optional[str] = None,
    exclude_below_set_lp_price: Optional[str] = None,
    side: Optional[str] = Query(None),
    q: Optional[str] = None,
    ordering: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    # Cold start after deploy: build snapshot once from local caches.
    if (
        not IndustryLpStoreOfferEconomics.objects.exists()
        and IndustryLpStoreOffer.objects.exists()
    ):
        rebuild_lp_store_offer_economics()

    page = query_lp_store_offers(
        currency=currency,
        exclude_tags=exclude_tags,
        exclude_supply_packages=exclude_supply_packages,
        exclude_chips=exclude_chips,
        exclude_skins=exclude_skins,
        exclude_useless_offers=exclude_useless_offers,
        exclude_below_set_lp_price=exclude_below_set_lp_price,
        side=side,
        q=q,
        ordering=ordering or DEFAULT_API_ORDERING,
        limit=limit,
        offset=offset,
        request=request,
    )
    items = [offer_economics_row_response(row) for row in page.rows]
    rebuilt_at = (
        page.rows[0].rebuilt_at
        if page.rows
        else IndustryLpStoreOfferEconomics.objects.aggregate(
            m=Max("rebuilt_at")
        )["m"]
    )
    return LoyaltyOffersListResponse(
        items=items,
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        rebuilt_at=rebuilt_at,
    )

"""GET /orders - LP buyback market order book (paginated)."""

from typing import Optional

from app.errors import ErrorResponse
from ninja import Query

from industry.endpoints.loyalty.schemas import LoyaltyMarketOrdersListResponse
from industry.endpoints.loyalty.serialization import market_order_response
from industry.helpers.lp_market_orders import ACTIVE_STATUSES
from industry.models import IndustryLoyaltyPointMarketOrder

PATH = "/orders"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List loyalty-point buy/sell market orders",
    "response": {200: LoyaltyMarketOrdersListResponse, 400: ErrorResponse},
}

MAX_LIMIT = 500
VALID_STATUSES = frozenset(
    value for value, _ in IndustryLoyaltyPointMarketOrder.Status.choices
)
ORDERINGS = {
    "created_at": ("created_at", "id"),
    "-created_at": ("-created_at", "-id"),
    "updated_at": ("updated_at", "id"),
    "-updated_at": ("-updated_at", "-id"),
}
DEFAULT_ORDERING = "-created_at"


def get_orders(
    request,
    side: Optional[str] = Query(None),
    loyalty_point_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    ordering: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """
    Order book listing. Defaults to active orders; pass ``status`` as a
    comma-separated list (e.g. ``completed,cancelled``) for history.
    Without ``limit`` the full filtered set is returned.
    """
    qs = IndustryLoyaltyPointMarketOrder.objects.select_related(
        "loyalty_point", "created_by", "claimed_by"
    ).prefetch_related("claims__claimed_by")
    if side:
        qs = qs.filter(side=side)
    if loyalty_point_id is not None:
        qs = qs.filter(loyalty_point_id=loyalty_point_id)
    if status:
        statuses = [s.strip().lower() for s in status.split(",") if s.strip()]
        unknown = [s for s in statuses if s not in VALID_STATUSES]
        if unknown:
            return 400, ErrorResponse(
                detail="Unknown status: " + ", ".join(sorted(unknown))
            )
        qs = qs.filter(status__in=statuses)
    else:
        qs = qs.filter(status__in=ACTIVE_STATUSES)

    order_fields = ORDERINGS.get(ordering or DEFAULT_ORDERING)
    if order_fields is None:
        return 400, ErrorResponse(
            detail="ordering must be one of: " + ", ".join(sorted(ORDERINGS))
        )
    qs = qs.order_by(*order_fields)

    total = qs.count()
    if limit is not None:
        rows = qs[offset : offset + limit]
    elif offset:
        rows = qs[offset:]
    else:
        rows = qs
    return LoyaltyMarketOrdersListResponse(
        items=[market_order_response(o) for o in rows],
        total=total,
        limit=limit,
        offset=offset,
    )

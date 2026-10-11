from ninja import Router, Schema
from ninja.errors import HttpError

from authentication import AuthBearer
from market.helpers.inferred_sales_monthly import build_monthly_response

router = Router(tags=["Market"])


class InferredSalesMonthlyTotals(Schema):
    fills: int
    units: int
    isk: float
    types: int


class InferredSalesMonthlyDay(Schema):
    date: str
    fills: int
    units: int
    isk: float


class InferredSalesMonthlyType(Schema):
    type_id: int
    name: str
    group: str
    category: str
    fills: int
    units: int
    isk: float


class InferredSalesMonthlyResponse(Schema):
    location_id: int
    year: int
    month: int
    start: str
    end: str
    totals: InferredSalesMonthlyTotals
    days: list[InferredSalesMonthlyDay]
    # Full by_type is extract-only (staff + include_types). Browsers use the
    # paginated /inferred-sales/monthly/types endpoint instead.
    by_type: list[InferredSalesMonthlyType] = []


@router.get(
    "/inferred-sales/monthly",
    description=(
        "Calendar-month inferred sell fills for a market location: totals and "
        "a per-day series. The full per-type breakdown is omitted unless "
        "include_types=true and the caller is staff (report extractor). "
        "Public type pages use /inferred-sales/monthly/types."
    ),
    response=InferredSalesMonthlyResponse,
    auth=AuthBearer(),
)
def get_inferred_sales_monthly(
    request,
    location_id: int,
    year: int,
    month: int,
    include_types: bool = False,
):
    try:
        payload = build_monthly_response(location_id, year, month)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc

    user = request.user
    may_dump = include_types and (
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
    )
    if not may_dump:
        payload = {**payload, "by_type": []}
    return payload

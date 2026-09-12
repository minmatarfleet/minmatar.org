from ninja import Router, Schema
from ninja.errors import HttpError

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
    by_type: list[InferredSalesMonthlyType]


@router.get(
    "/inferred-sales/monthly",
    description=(
        "Calendar-month inferred sell fills for a market location: totals, "
        "a per-day series and a per-type breakdown (ISK = quantity x fill "
        "price). Feeds the public monthly market report."
    ),
    response=InferredSalesMonthlyResponse,
)
def get_inferred_sales_monthly(
    request,
    location_id: int,
    year: int,
    month: int,
):
    try:
        return build_monthly_response(location_id, year, month)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc

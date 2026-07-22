from ninja import Router, Schema

from market.helpers.inferred_sales import build_volume_response

router = Router(tags=["Market"])


class InferredSalesVolumeBucket(Schema):
    date: str
    units: int


class InferredSalesVelocity(Schema):
    long_days: int
    short_days: int
    days_of_data: int
    median_daily_units: float
    short_mean_daily_units: float
    total_units: int


class InferredSalesTopMover(Schema):
    type_id: int
    item_name: str
    units: int


class InferredSalesVolumeResponse(Schema):
    location_id: int
    days: int
    buckets: list[InferredSalesVolumeBucket]
    velocity: InferredSalesVelocity
    top_movers: list[InferredSalesTopMover]


@router.get(
    "/inferred-sales/volume",
    description=(
        "Day-bucketed inferred sell volume and velocity for a market location, "
        "derived from successive structure order-book snapshots."
    ),
    response=InferredSalesVolumeResponse,
)
def get_inferred_sales_volume(
    request,
    location_id: int,
    type_id: int | None = None,
    days: int = 7,
):
    return build_volume_response(location_id, days=days, type_id=type_id)

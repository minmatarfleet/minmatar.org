from django.contrib.auth.models import AnonymousUser
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.responses import Response

from authentication import AuthOptional
from market.helpers.inferred_sales_monthly_volume import (
    PAGE_SIZE,
    build_volume_page,
)
from market.helpers.inferred_sales_volume_rate_limit import (
    VolumeRateLimited,
    enforce_volume_rate_limit,
)

router = Router(tags=["Market"])


class InferredSalesMonthlyVolumeClass(Schema):
    slug: str
    label: str
    count: int


class InferredSalesMonthlyVolumeRow(Schema):
    type_id: int
    name: str
    group: str
    category: str
    fills: int
    units: int
    isk: float
    isk_label: str
    amamake_avg: float
    jita: float | None
    freight: float
    markup_pct: float | None
    extra_isk: float | None
    extra_isk_label: str | None


class InferredSalesMonthlyVolumeResponse(Schema):
    location_id: int
    year: int
    month: int
    page: int
    page_size: int
    total: int
    total_pages: int
    sort: str
    sold_class: str
    q: str
    classes: list[InferredSalesMonthlyVolumeClass]
    rows: list[InferredSalesMonthlyVolumeRow]


def _is_anonymous(request) -> bool:
    auth = getattr(request, "auth", None)
    if auth is None or isinstance(auth, AnonymousUser):
        user = getattr(request, "user", None)
        return (
            user is None
            or isinstance(user, AnonymousUser)
            or not getattr(user, "is_authenticated", False)
        )
    return False


@router.get(
    "/inferred-sales/monthly/types",
    description=(
        "One page of monthly inferred-sales types for the Amamake report "
        f"(fixed page_size={PAGE_SIZE}). Anonymous callers can page and "
        "filter within a small per-IP budget; further use asks for login. "
        "Never re-aggregates fills — slices the cached monthly list."
    ),
    response={
        200: InferredSalesMonthlyVolumeResponse,
        400: dict,
        401: dict,
        429: dict,
    },
    auth=AuthOptional(),
)
def get_inferred_sales_monthly_types(
    request,
    location_id: int,
    year: int,
    month: int,
    page: int = 1,
    sort: str = "isk",
    sold_class: str = "all",
    q: str = "",
    page_size: int | None = None,
):
    # page_size is intentionally ignored — fixed server-side to stop scrapers
    # asking for the full catalog in one shot.
    del page_size

    try:
        enforce_volume_rate_limit(request)
    except VolumeRateLimited as exc:
        headers = {"Retry-After": str(int(exc.retry_after))}
        if exc.login_suggested or _is_anonymous(request):
            return Response(
                {"detail": "login_required"},
                status=401,
                headers=headers,
            )
        return Response(
            {"detail": "rate_limited"},
            status=429,
            headers=headers,
        )

    try:
        return build_volume_page(
            location_id,
            year,
            month,
            page=page,
            sort=sort,
            sold_class=sold_class,
            q=q,
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc

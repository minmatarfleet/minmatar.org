"""GET /contracts/history/csv – detailed finished freight contracts CSV."""

from datetime import datetime, timezone as dt_timezone

from django.http import HttpResponse
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from freight.helpers.contracts_csv import render_freight_history_csv
from freight.models import FreightContract

router = Router(tags=["Freight"])


@router.get(
    "/history/csv",
    auth=AuthBearer(),
    description=(
        "Download finished freight contracts as CSV with full location, "
        "character, corporation, and date detail. Requires authentication."
    ),
    response={200: None, 401: ErrorResponse},
)
def get_contracts_history_csv(request):
    contracts = list(
        FreightContract.objects.finished().order_by("-date_completed")
    )
    csv_text = render_freight_history_csv(contracts)
    stamp = datetime.now(dt_timezone.utc).strftime("%Y%m%d")
    response = HttpResponse(
        csv_text,
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="freight-contracts-history-{stamp}.csv"'
    )
    return response

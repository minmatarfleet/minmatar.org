"""GET /settings - every LP corp with its accounts and contacts."""

from typing import List

from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    SettingsCurrency,
    can_edit_settings,
    currency_schema,
    forbidden,
)
from industry.models import IndustryLoyaltyPoint

PATH = "/settings"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "LP buyback configuration: corps, accounts and contacts",
    "auth": AuthBearer(),
    "response": {200: List[SettingsCurrency], 403: ErrorResponse},
}


def get_settings(request):
    if not can_edit_settings(request.user):
        return forbidden()
    currencies = IndustryLoyaltyPoint.objects.prefetch_related(
        "accounts__contacts"
    ).order_by("name")
    return 200, [currency_schema(c) for c in currencies]

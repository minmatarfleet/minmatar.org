"""GET /settings/currencies/{id}/history - the corp's recent ISK/LP changes."""

from typing import List

from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    SettingsPriceChange,
    can_edit_settings,
    forbidden,
    price_change_schema,
    price_history,
)
from industry.models import IndustryLoyaltyPoint

PATH = "/settings/currencies/{currency_id}/history"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Recent ISK/LP changes of an LP corp, newest first",
    "auth": AuthBearer(),
    "response": {
        200: List[SettingsPriceChange],
        403: ErrorResponse,
        404: ErrorResponse,
    },
}

HISTORY_LIMIT = 20


def get_settings_history(request, currency_id: int):
    if not can_edit_settings(request.user):
        return forbidden()
    if not IndustryLoyaltyPoint.objects.filter(pk=currency_id).exists():
        return 404, ErrorResponse.new("LP corp not found")
    return 200, [
        price_change_schema(change)
        for change in price_history(currency_id, HISTORY_LIMIT)
    ]

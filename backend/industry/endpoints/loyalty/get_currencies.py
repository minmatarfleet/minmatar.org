"""GET /currencies - active LP currencies with published ISK/LP rates."""

from typing import List

from industry.endpoints.loyalty.schemas import LoyaltyCurrencyResponse
from industry.endpoints.loyalty.serialization import currency_response
from industry.models import IndustryLoyaltyPoint

PATH = "/currencies"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List active loyalty-point currencies and default ISK/LP rates",
    "response": {200: List[LoyaltyCurrencyResponse]},
}


def get_currencies(request):
    currencies = IndustryLoyaltyPoint.objects.filter(is_active=True).order_by(
        "name"
    )
    return [currency_response(c) for c in currencies]

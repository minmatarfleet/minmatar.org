"""POST /settings/currencies - add an LP corp we buy."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    CurrencyCreateRequest,
    SettingsCurrency,
    can_edit_settings,
    currency_schema,
    forbidden,
)
from industry.models import IndustryLoyaltyPoint

PATH = "/settings/currencies"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Add an LP corp",
    "auth": AuthBearer(),
    "response": {
        200: SettingsCurrency,
        400: ErrorResponse,
        403: ErrorResponse,
    },
}


def post_settings_currency(request, payload: CurrencyCreateRequest):
    if not can_edit_settings(request.user):
        return forbidden()
    if IndustryLoyaltyPoint.objects.filter(
        corporation_id=payload.corporation_id
    ).exists():
        return 400, ErrorResponse.new("That corporation is already set up")
    currency = IndustryLoyaltyPoint.objects.create(
        name=payload.name,
        corporation_id=payload.corporation_id,
        default_isk_per_lp=payload.default_isk_per_lp,
        express_isk_per_lp=payload.express_isk_per_lp,
    )
    record_change(request.user, f"LP corp added: {currency.name}")
    return 200, currency_schema(currency)

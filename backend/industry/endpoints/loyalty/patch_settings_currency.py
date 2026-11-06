"""PATCH /settings/currencies/{id} - enable, disable or reprice an LP corp."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    CurrencyPatchRequest,
    SettingsCurrency,
    can_edit_settings,
    currency_schema,
    forbidden,
)
from industry.models import IndustryLoyaltyPoint

PATH = "/settings/currencies/{currency_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Edit an LP corp",
    "auth": AuthBearer(),
    "response": {
        200: SettingsCurrency,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}

FIELDS = (
    "name",
    "default_isk_per_lp",
    "express_isk_per_lp",
    "is_active",
    "allow_buy",
    "allow_sell",
    "notes",
)


def patch_settings_currency(
    request, currency_id: int, payload: CurrencyPatchRequest
):
    if not can_edit_settings(request.user):
        return forbidden()
    currency = IndustryLoyaltyPoint.objects.filter(pk=currency_id).first()
    if currency is None:
        return 404, ErrorResponse.new("LP corp not found")
    changes = []
    for field in FIELDS:
        value = getattr(payload, field)
        if value is not None and value != getattr(currency, field):
            changes.append(f"{field} {getattr(currency, field)} -> {value}")
            setattr(currency, field, value)
    if payload.clear_express and currency.express_isk_per_lp is not None:
        changes.append(
            f"express_isk_per_lp {currency.express_isk_per_lp} -> off"
        )
        currency.express_isk_per_lp = None
    if changes:
        # The model writes price history with this actor.
        currency.history_changed_by = request.user
        currency.save()
        record_change(
            request.user,
            f"LP corp {currency.name}: " + "; ".join(changes),
        )
    return 200, currency_schema(currency)

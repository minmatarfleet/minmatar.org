"""POST /settings/accounts - add a seller or stockpile account."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    AccountCreateRequest,
    SettingsAccount,
    account_schema,
    can_edit_settings,
    forbidden,
)
from industry.models import IndustryLoyaltyPoint, IndustryLoyaltyPointAccount

PATH = "/settings/accounts"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Add an LP account",
    "auth": AuthBearer(),
    "response": {
        200: SettingsAccount,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_settings_account(request, payload: AccountCreateRequest):
    if not can_edit_settings(request.user):
        return forbidden()
    currency = IndustryLoyaltyPoint.objects.filter(
        pk=payload.loyalty_point_id
    ).first()
    if currency is None:
        return 404, ErrorResponse.new("LP corp not found")
    if payload.role not in IndustryLoyaltyPointAccount.Role.values:
        return 400, ErrorResponse.new("Unknown account role")
    if IndustryLoyaltyPointAccount.objects.filter(
        loyalty_point=currency, name=payload.name, is_active=True
    ).exists():
        return 400, ErrorResponse.new("An active account has that name")
    account = IndustryLoyaltyPointAccount(
        loyalty_point=currency,
        name=payload.name,
        role=payload.role,
        isk_per_lp=payload.isk_per_lp,
        corporation_name=payload.corporation_name,
        notes=payload.notes,
    )
    account.history_changed_by = request.user
    account.save()
    record_change(
        request.user,
        f"LP account added: {account.name} ({currency.name})",
    )
    return 200, account_schema(account)

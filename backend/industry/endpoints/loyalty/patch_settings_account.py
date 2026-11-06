"""PATCH /settings/accounts/{id} - edit or retire an LP account."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    AccountPatchRequest,
    SettingsAccount,
    account_schema,
    can_edit_settings,
    forbidden,
)
from industry.models import IndustryLoyaltyPointAccount

PATH = "/settings/accounts/{account_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Edit an LP account",
    "auth": AuthBearer(),
    "response": {
        200: SettingsAccount,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}

FIELDS = (
    "name",
    "role",
    "isk_per_lp",
    "corporation_name",
    "notes",
    "is_active",
)


def patch_settings_account(
    request, account_id: int, payload: AccountPatchRequest
):
    if not can_edit_settings(request.user):
        return forbidden()
    account = IndustryLoyaltyPointAccount.objects.filter(pk=account_id).first()
    if account is None:
        return 404, ErrorResponse.new("Account not found")
    if (
        payload.role is not None
        and payload.role not in IndustryLoyaltyPointAccount.Role.values
    ):
        return 400, ErrorResponse.new("Unknown account role")
    changes = []
    for field in FIELDS:
        value = getattr(payload, field)
        if value is not None and value != getattr(account, field):
            changes.append(f"{field} {getattr(account, field)} -> {value}")
            setattr(account, field, value)
    if payload.clear_isk_per_lp and account.isk_per_lp is not None:
        changes.append(f"isk_per_lp {account.isk_per_lp} -> default")
        account.isk_per_lp = None
    if changes:
        account.history_changed_by = request.user
        account.save()
        record_change(
            request.user,
            f"LP account {account.name}: " + "; ".join(changes),
        )
    return 200, account_schema(account)

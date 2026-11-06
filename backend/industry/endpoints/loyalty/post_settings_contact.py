"""POST /settings/contacts - add a contact to an LP account."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    ContactCreateRequest,
    SettingsContact,
    can_edit_settings,
    contact_schema,
    forbidden,
)
from industry.models import (
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
)

PATH = "/settings/contacts"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Add an LP account contact",
    "auth": AuthBearer(),
    "response": {
        200: SettingsContact,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_settings_contact(request, payload: ContactCreateRequest):
    if not can_edit_settings(request.user):
        return forbidden()
    account = IndustryLoyaltyPointAccount.objects.filter(
        pk=payload.account_id
    ).first()
    if account is None:
        return 404, ErrorResponse.new("Account not found")
    contact = IndustryLoyaltyPointContact.objects.create(
        account=account,
        character_name=payload.character_name,
        discord_username=payload.discord_username,
        notes=payload.notes,
    )
    record_change(
        request.user,
        f"LP contact added: {contact.character_name} ({account.name})",
    )
    return 200, contact_schema(contact)

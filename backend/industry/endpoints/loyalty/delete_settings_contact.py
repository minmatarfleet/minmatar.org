"""DELETE /settings/contacts/{id} - remove a contact."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    can_edit_settings,
    forbidden,
)
from industry.models import IndustryLoyaltyPointContact

PATH = "/settings/contacts/{contact_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Remove an LP account contact",
    "auth": AuthBearer(),
    "response": {200: dict, 403: ErrorResponse, 404: ErrorResponse},
}


def delete_settings_contact(request, contact_id: int):
    if not can_edit_settings(request.user):
        return forbidden()
    contact = IndustryLoyaltyPointContact.objects.filter(pk=contact_id).first()
    if contact is None:
        return 404, ErrorResponse.new("Contact not found")
    name = contact.character_name
    contact.delete()
    record_change(request.user, f"LP contact removed: {name}")
    return 200, {"deleted": True}

"""PATCH /settings/contacts/{id} - edit or retire a contact."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from industry.endpoints.loyalty.settings_common import (
    ContactPatchRequest,
    SettingsContact,
    can_edit_settings,
    contact_schema,
    forbidden,
)
from industry.models import IndustryLoyaltyPointContact

PATH = "/settings/contacts/{contact_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Edit an LP account contact",
    "auth": AuthBearer(),
    "response": {
        200: SettingsContact,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}

FIELDS = ("character_name", "discord_username", "notes", "is_active")


def patch_settings_contact(
    request, contact_id: int, payload: ContactPatchRequest
):
    if not can_edit_settings(request.user):
        return forbidden()
    contact = IndustryLoyaltyPointContact.objects.filter(pk=contact_id).first()
    if contact is None:
        return 404, ErrorResponse.new("Contact not found")
    changes = []
    for field in FIELDS:
        value = getattr(payload, field)
        if value is not None and value != getattr(contact, field):
            changes.append(field)
            setattr(contact, field, value)
    if changes:
        contact.save()
        record_change(
            request.user,
            f"LP contact {contact.character_name}: " + ", ".join(changes),
        )
    return 200, contact_schema(contact)

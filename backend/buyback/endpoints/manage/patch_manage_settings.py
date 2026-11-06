"""PATCH /manage/settings - rates, location and on/off."""

from audit.helpers import record_change
from authentication import AuthBearer
from app.errors import ErrorResponse
from buyback.endpoints.manage.common import (
    ManageSettings,
    SettingsPatchRequest,
    can_manage,
    forbidden,
    settings_schema,
)
from buyback.models import EveBuybackSettings
from eveonline.models import EveLocation

PATH = "/manage/settings"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Edit buyback rates and location",
    "auth": AuthBearer(),
    "response": {
        200: ManageSettings,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}

RATE_FIELDS = ("ore_refine", "demand_jita_buy", "surplus_jita_buy")


def patch_manage_settings(request, payload: SettingsPatchRequest):
    if not can_manage(request.user):
        return forbidden()
    settings = EveBuybackSettings.load()
    changes = []
    for field in ("active", *RATE_FIELDS):
        value = getattr(payload, field)
        if value is not None and value != getattr(settings, field):
            changes.append(f"{field} {getattr(settings, field)} -> {value}")
            setattr(settings, field, value)
    if payload.location_id is not None:
        location = EveLocation.objects.filter(
            location_id=payload.location_id
        ).first()
        if location is None:
            return 404, ErrorResponse.new("Location not found")
        if settings.location_id != location.location_id:
            changes.append(f"location -> {location.location_name}")
            settings.location = location
    elif payload.clear_location and settings.location_id is not None:
        changes.append("location cleared")
        settings.location = None
    if changes:
        settings.save()
        record_change(request.user, "Buyback settings: " + "; ".join(changes))
    return 200, settings_schema()

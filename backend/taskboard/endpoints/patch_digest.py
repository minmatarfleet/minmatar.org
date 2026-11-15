"""PATCH "/digest" - turn the weekly list on or off, set its day and hour."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import can_manage_settings
from taskboard.endpoints.get_digest import digest_row
from taskboard.models import TaskDigestSettings
from taskboard.schemas import DigestSettingsPatch, DigestSettingsResponse

PATH = "/digest"
METHOD = "patch"
ROUTE_SPEC = {
    "tags": ["Tasks - Settings"],
    "response": {
        200: DigestSettingsResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Change when the weekly list goes out",
}


def patch_digest(request, payload: DigestSettingsPatch):
    if not can_manage_settings(request.user):
        return 403, ErrorResponse(detail="Only task admins change this.")
    if payload.weekday is not None and not 0 <= payload.weekday <= 6:
        return 400, ErrorResponse(detail="Pick a day of the week.")
    if payload.hour is not None and not 0 <= payload.hour <= 23:
        return 400, ErrorResponse(detail="Pick an hour from 0 to 23.")
    settings = TaskDigestSettings.load()
    for name in ("enabled", "weekday", "hour"):
        value = getattr(payload, name)
        if value is not None:
            setattr(settings, name, value)
    settings.save()
    return 200, digest_row()

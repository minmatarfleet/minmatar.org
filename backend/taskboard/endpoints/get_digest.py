"""GET "/digest" - when the weekly list goes out, and the last send."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.access import can_manage_settings
from taskboard.messages import weekly_stats
from taskboard.models import TaskDigestSettings
from taskboard.schemas import DigestSettingsResponse

PATH = "/digest"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks - Settings"],
    "response": {200: DigestSettingsResponse, 403: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "The weekly list: day, hour, and what the last send did",
}


def digest_row() -> dict:
    settings = TaskDigestSettings.load()
    return {
        "enabled": settings.enabled,
        "weekday": settings.weekday,
        "hour": settings.hour,
        **weekly_stats(),
    }


def get_digest(request):
    if not can_manage_settings(request.user):
        return 403, ErrorResponse(detail="Only task admins see this.")
    return 200, digest_row()

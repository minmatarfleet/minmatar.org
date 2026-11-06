"""GET /manage/settings - editable buyback configuration."""

from authentication import AuthBearer
from app.errors import ErrorResponse
from buyback.endpoints.manage.common import (
    ManageSettings,
    can_manage,
    forbidden,
    settings_schema,
)

PATH = "/manage/settings"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Buyback settings and accepted items for the editor",
    "auth": AuthBearer(),
    "response": {200: ManageSettings, 403: ErrorResponse},
}


def get_manage_settings(request):
    if not can_manage(request.user):
        return forbidden()
    return 200, settings_schema()

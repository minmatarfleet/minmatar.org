"""GET "/preferences" - the pilot's own task switches."""

from authentication import AuthBearer
from groups.models import UserCommunityStatus
from taskboard.schemas import TaskPreferencesResponse
from taskboard.services import preferences


def preference_row(user) -> dict:
    prefs = preferences(user)
    return {
        "show_suggestions": prefs.show_suggestions,
        "paused": prefs.paused,
        "on_leave": UserCommunityStatus.objects.filter(
            user=user, status=UserCommunityStatus.STATUS_ON_LEAVE
        ).exists(),
    }


PATH = "/preferences"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: TaskPreferencesResponse},
    "auth": AuthBearer(),
    "summary": "Show suggestions, and whether tasks are paused",
}


def get_preferences(request):
    return 200, preference_row(request.user)

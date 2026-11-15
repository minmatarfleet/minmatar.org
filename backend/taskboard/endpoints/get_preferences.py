"""GET "/preferences" - the pilot's own task switches."""

from authentication import AuthBearer
from groups.models import UserCommunityStatus
from taskboard.messages import weekly_dm_enabled
from taskboard.schemas import TaskPreferencesResponse
from taskboard.services import preferences


def preference_row(user) -> dict:
    prefs = preferences(user)
    return {
        "show_suggestions": prefs.show_suggestions,
        "paused": prefs.paused,
        "weekly_dm": weekly_dm_enabled(user),
        "quiet_start": prefs.quiet_start,
        "quiet_end": prefs.quiet_end,
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

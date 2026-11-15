"""PATCH "/preferences" - show suggestions, pause my tasks."""

from authentication import AuthBearer
from taskboard.endpoints.get_preferences import preference_row
from taskboard.schemas import TaskPreferencesPatch, TaskPreferencesResponse
from taskboard.services import preferences

PATH = "/preferences"
METHOD = "patch"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: TaskPreferencesResponse},
    "auth": AuthBearer(),
    "summary": "Change the pilot's own task switches",
}


def patch_preferences(request, payload: TaskPreferencesPatch):
    prefs = preferences(request.user)
    changed = []
    for name in ("show_suggestions", "paused"):
        value = getattr(payload, name)
        if value is not None:
            setattr(prefs, name, value)
            changed.append(name)
    if changed:
        prefs.save(update_fields=changed)
    return 200, preference_row(request.user)

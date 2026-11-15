"""PATCH "/preferences" - show suggestions, pause my tasks."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from taskboard.endpoints.get_preferences import preference_row
from taskboard.schemas import TaskPreferencesPatch, TaskPreferencesResponse
from taskboard.messages import set_weekly_dm
from taskboard.services import preferences

PATH = "/preferences"
METHOD = "patch"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: TaskPreferencesResponse, 400: ErrorResponse},
    "auth": AuthBearer(),
    "summary": "Change the pilot's own task switches",
}


def patch_preferences(request, payload: TaskPreferencesPatch):
    for hour in (payload.quiet_start, payload.quiet_end):
        if hour is not None and not 0 <= hour <= 23:
            return 400, ErrorResponse(detail="Pick an hour from 0 to 23.")
    if payload.weekly_dm is not None:
        set_weekly_dm(request.user, payload.weekly_dm)
    prefs = preferences(request.user)
    changed = []
    for name in ("show_suggestions", "paused", "quiet_start", "quiet_end"):
        value = getattr(payload, name)
        if value is not None:
            setattr(prefs, name, value)
            changed.append(name)
    if payload.clear_quiet_hours:
        prefs.quiet_start = prefs.quiet_end = None
        changed += ["quiet_start", "quiet_end"]
    if changed:
        prefs.save(update_fields=sorted(set(changed)))
    return 200, preference_row(request.user)

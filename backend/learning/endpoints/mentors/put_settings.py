"""PUT "/settings" - save the mentor's times and capacity."""

from authentication import AuthBearer
from learning.endpoints.mentors.common import ERRORS, handles_errors
from learning.mentors import availability as avail
from learning.mentors import service, views
from learning.mentors.schemas import MentorSettingsBody, MentorSettingsResponse
from learning.mentors.service import MentorError

PATH = "/settings"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Save the mentor's weekday and weekend times and capacity.",
    "auth": AuthBearer(),
    "response": {200: MentorSettingsResponse, **ERRORS},
}


@handles_errors
def put_settings(request, payload: MentorSettingsBody):
    profile = service.profile_for(request.user)
    if profile is None:
        raise MentorError("You aren't a mentor.", 403)
    available = avail.Availability.build(
        payload.weekday_brackets, payload.weekend_brackets, payload.days
    )
    if not 1 <= payload.classes_per_week <= 10:
        raise MentorError("Classes a week must be 1 to 10.")
    profile.weekday_brackets = list(available.weekday_brackets)
    profile.weekend_brackets = list(available.weekend_brackets)
    profile.days = list(available.days)
    profile.classes_per_week = payload.classes_per_week
    profile.taking_requests = payload.taking_requests
    profile.save()
    return 200, views.settings(request.user)

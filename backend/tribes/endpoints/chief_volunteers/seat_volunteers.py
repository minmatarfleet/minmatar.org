"""GET/POST "/{tribe_id}/chief-volunteers" - an open seat's volunteers.

POST: the viewer volunteers (tribe seat, or one of ``tribe_group_id``'s
timezone seats).
GET: the executor lists a seat's pending offers (a group's three seats
together unless ``region`` names one).
"""

from typing import List, Optional

from authentication import AuthBearer
from tribes.endpoints.chief_volunteers.schemas import (
    ChiefVolunteerSchema,
    VolunteerRequest,
)
from tribes.endpoints.chief_volunteers.serializers import serialize_volunteer
from tribes.helpers.chief_regions import clean_region
from tribes.helpers.chiefs import (
    ChiefVolunteerError,
    pending_volunteers,
    user_is_executor,
    volunteer,
)
from tribes.models import Tribe, TribeGroup

PATH = "/{tribe_id}/chief-volunteers"

GET_ROUTE_SPEC = {
    "summary": "Pending chief volunteers for an open seat (executor only).",
    "response": {200: List[ChiefVolunteerSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}

POST_ROUTE_SPEC = {
    "summary": "Volunteer to lead a tribe or group that has no chief.",
    "response": {
        201: ChiefVolunteerSchema,
        400: dict,
        404: dict,
        503: dict,
    },
    "auth": AuthBearer(),
}


def _seat(tribe_id: int, tribe_group_id: Optional[int]):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if tribe is None:
        return None, None, "Tribe not found."
    if tribe_group_id is None:
        return tribe, None, ""
    tribe_group = TribeGroup.objects.filter(
        pk=tribe_group_id, tribe=tribe
    ).first()
    if tribe_group is None:
        return None, None, "TribeGroup not found."
    return tribe, tribe_group, ""


def get_chief_volunteers(
    request,
    tribe_id: int,
    tribe_group_id: Optional[int] = None,
    region: Optional[str] = None,
):
    if not user_is_executor(request.user):
        return 403, {"detail": "Only the alliance executor sees volunteers."}
    tribe, tribe_group, missing = _seat(tribe_id, tribe_group_id)
    if missing:
        return 404, {"detail": missing}
    return 200, [
        serialize_volunteer(offer)
        for offer in pending_volunteers(
            tribe, tribe_group, clean_region(region)
        ).select_related("tribe", "tribe_group")
    ]


def post_chief_volunteer(request, tribe_id: int, payload: VolunteerRequest):
    tribe, tribe_group, missing = _seat(tribe_id, payload.tribe_group_id)
    if missing:
        return 404, {"detail": missing}
    try:
        offer = volunteer(
            request.user,
            tribe,
            tribe_group,
            payload.note,
            region=payload.region,
        )
    except ChiefVolunteerError as exc:
        return exc.status_code, {"detail": str(exc)}
    return 201, serialize_volunteer(offer)

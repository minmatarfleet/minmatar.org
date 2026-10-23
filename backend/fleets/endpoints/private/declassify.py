"""POST /{fleet_id}/declassify — make a finished private fleet a normal one."""

from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.endpoints.private.invites import _private_fleet
from fleets.helpers.private_fleets import PrivateFleetError, declassify


class DeclassifiedResponse(BaseModel):
    fleet_id: int
    declassified_at: str


def post_declassify(request, fleet_id: int):
    fleet = _private_fleet(request, fleet_id)
    if isinstance(fleet, tuple):
        return fleet
    try:
        declassify(fleet)
    except PrivateFleetError as exc:
        return exc.status_code, ErrorResponse(detail=str(exc))
    return 200, DeclassifiedResponse(
        fleet_id=fleet.id, declassified_at=fleet.declassified_at.isoformat()
    )


ROUTES = (
    (
        "post",
        "/{fleet_id}/declassify",
        {
            "auth": AuthBearer(),
            "response": {
                200: DeclassifiedResponse,
                400: ErrorResponse,
                404: None,
            },
            "description": (
                "After a private fleet, its FC or a Strategic FC makes it "
                "a normal fleet: history, kills, battle report and metrics. "
                "Invites, answers and the thread stay private."
            ),
        },
        post_declassify,
    ),
)

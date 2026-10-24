"""GET /window/mine — the desktop window's Recent tab and the user's sign-ups."""

from authentication import AuthBearer

from fleets.endpoints.helpers import etag_json_response
from fleets.endpoints.schemas import MyFleetsResponse
from fleets.helpers.my_fleets import my_signups, recent_fleets

PATH = "/window/mine"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: MyFleetsResponse, 304: None},
    "description": (
        "The fleets the user flew in or commanded in the last 30 days "
        "(newest first, with their own losses and each loss's SRP state), "
        "how many of those losses have no SRP request, and the user's ship "
        "sign-ups for fleets that haven't ended. Sends an ETag; a matching "
        "If-None-Match gets 304."
    ),
}


def get_my_fleets(request):
    recent = recent_fleets(request.user)
    return etag_json_response(
        request,
        MyFleetsResponse(
            fleets=recent["fleets"],
            srp_owed=recent["srp_owed"],
            signups=my_signups(request.user),
        ),
    )

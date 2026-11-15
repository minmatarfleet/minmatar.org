"""GET "/mine" - everything waiting on the signed-in pilot."""

from authentication import AuthBearer
from taskboard.queries import my_tasks
from taskboard.schemas import MyTasksResponse
from taskboard.sync import sync_user

PATH = "/mine"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: MyTasksResponse},
    "auth": AuthBearer(),
    "summary": "My tasks: what needs me, suggestions, team work up for grabs",
}


def get_my_tasks(request):
    # Their own automatic tasks refresh now, so a fixed token clears at once.
    sync_user(request.user)
    return 200, my_tasks(request.user)

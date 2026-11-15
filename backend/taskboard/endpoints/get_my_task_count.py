"""GET "/mine/count" - the Neocom count."""

from authentication import AuthBearer
from taskboard.queries import needs_you_count
from taskboard.schemas import TaskCountResponse

PATH = "/mine/count"
METHOD = "get"
ROUTE_SPEC = {
    "tags": ["Tasks"],
    "response": {200: TaskCountResponse},
    "auth": AuthBearer(),
    "summary": "How many open tasks need the signed-in pilot",
}


def get_my_task_count(request):
    return 200, {"needs_you": needs_you_count(request.user)}

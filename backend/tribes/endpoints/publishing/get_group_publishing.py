"""GET "/groups/{group_id}/publishing" (registered in __init__ with PATCH) - a group's publishing settings."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from tribes.endpoints.publishing.schemas import TribeGroupPublishingSchema
from tribes.endpoints.publishing.serializers import serialize_publishing
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup

PATH = "/groups/{group_id}/publishing"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Who may publish as the group, and its Discord channel.",
    "description": "Managers of the group only.",
    "response": {
        200: TribeGroupPublishingSchema,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
}


def get_group_publishing(request, group_id: int):
    group = (
        TribeGroup.objects.filter(pk=group_id)
        .select_related("tribe", "group__discord_group")
        .first()
    )
    if group is None:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, group):
        return 403, {"detail": "Only the group's managers can see this."}
    return 200, serialize_publishing(group)

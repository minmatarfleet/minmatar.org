"""GET "/{tribe_id}/groups/{group_id}" - tribe group detail."""

from ninja import Router

from authentication import AuthOptional
from tribes.endpoints.groups.schemas import TribeGroupSchema
from tribes.endpoints.groups.serializers import serialize_tribe_group
from tribes.models import TribeGroup

PATH = "/{tribe_id}/groups/{group_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Tribe group detail with requirements.",
    "response": {200: TribeGroupSchema, 404: dict},
    "auth": AuthOptional(),
}

router = Router(tags=["Tribes - Groups"])


def get_tribe_group(request, tribe_id: int, group_id: int):
    tg = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .select_related("chief__eveplayer__primary_character", "tribe")
        .prefetch_related(
            "allowed_affiliations",
            "ranks",
            "requirements__asset_types__eve_type",
            "requirements__asset_types__locations",
            "requirements__qualifying_skills__eve_type",
        )
        .first()
    )
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    return 200, serialize_tribe_group(tg, request_user=request.user)


router.get(PATH, **ROUTE_SPEC)(get_tribe_group)

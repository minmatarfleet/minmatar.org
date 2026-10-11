"""GET "/{tribe_id}" - tribe detail."""

from ninja import Router

from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribes.serializers import serialize_tribe
from tribes.models import Tribe

PATH = "/{tribe_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Tribe detail.",
    "response": {200: TribeSchema, 404: dict},
}

router = Router(tags=["Tribes"])


def get_tribe(request, tribe_id: int):
    tribe = (
        Tribe.objects.filter(pk=tribe_id)
        .select_related(
            "chief__eveplayer__primary_character",
        )
        .first()
    )
    if not tribe:
        return 404, {"detail": "Tribe not found."}
    return 200, serialize_tribe(tribe)


router.get(PATH, **ROUTE_SPEC)(get_tribe)

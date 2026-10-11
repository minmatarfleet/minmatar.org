"""GET "" - list all active tribes."""

from typing import List

from ninja import Router

from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribes.serializers import serialize_tribe
from tribes.models import Tribe

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all active tribes.",
    "response": {200: List[TribeSchema]},
}

router = Router(tags=["Tribes"])


def get_tribes(request):
    return [
        serialize_tribe(tribe)
        for tribe in (
            Tribe.objects.filter(is_active=True)
            .select_related(
                "chief__eveplayer__primary_character",
            )
            .prefetch_related("groups")
        )
    ]


router.get(PATH, **ROUTE_SPEC)(get_tribes)

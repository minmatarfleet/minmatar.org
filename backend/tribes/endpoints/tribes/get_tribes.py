"""GET "" - list all active tribes."""

from typing import List


from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribes.serializers import serialize_tribe
from tribes.helpers.chiefs import ChiefResolver
from tribes.models import Tribe

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all active tribes.",
    "response": {200: List[TribeSchema]},
}


def get_tribes(request):
    resolver = ChiefResolver()
    return [
        serialize_tribe(tribe, resolver=resolver)
        for tribe in (
            Tribe.objects.filter(is_active=True)
            .select_related(
                "chief__eveplayer__primary_character",
            )
            .prefetch_related("groups")
        )
    ]

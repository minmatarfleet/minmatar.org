"""GET "" - list active tribes, or archived ones for structure managers."""

from typing import List

from authentication import AuthOptional
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribes.serializers import serialize_tribe
from tribes.helpers.chiefs import ChiefResolver
from tribes.helpers.structure import can_manage_structure
from tribes.models import Tribe

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List active tribes (archived=true: archived ones).",
    "description": "archived=true needs tribes.structure.manage.",
    "response": {200: List[TribeSchema], 403: dict},
    "auth": AuthOptional(),
}


def get_tribes(request, archived: bool = False):
    if archived and not can_manage_structure(request.user):
        return 403, {"detail": "Only structure managers see archived tribes."}
    resolver = ChiefResolver()
    return 200, [
        serialize_tribe(tribe, resolver=resolver)
        for tribe in (
            Tribe.objects.filter(is_active=not archived)
            .select_related(
                "chief__eveplayer__primary_character",
            )
            .prefetch_related("groups")
        )
    ]

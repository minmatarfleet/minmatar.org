"""GET "/{tribe_id}/groups" - active groups, or archived ones for managers."""

from typing import List

from django.db.models import Count, Q

from authentication import AuthOptional
from tribes.endpoints.groups.schemas import TribeGroupSchema
from tribes.endpoints.groups.serializers import serialize_tribe_group
from tribes.helpers.publishing import active_member_group_ids
from tribes.helpers.chiefs import ChiefResolver
from tribes.helpers.structure import can_manage_structure
from tribes.models import Tribe, TribeGroupMembership

PATH = "/{tribe_id}/groups"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List active groups in a tribe (archived=true: archived ones).",
    "description": "archived=true needs tribes.structure.manage.",
    "response": {200: List[TribeGroupSchema], 403: dict, 404: dict},
    "auth": AuthOptional(),
}


def get_tribe_groups(request, tribe_id: int, archived: bool = False):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if not tribe:
        return 404, {"detail": "Tribe not found."}
    if archived and not can_manage_structure(request.user):
        return 403, {"detail": "Only structure managers see archived groups."}

    groups = (
        tribe.groups.filter(is_active=not archived)
        .select_related(
            "tribe__chief__eveplayer__primary_character",
            "group__discord_group",
        )
        .prefetch_related(
            "chief_seats__user__eveplayer__primary_character",
            "allowed_affiliations",
            "ranks",
            "requirements__asset_types__eve_type",
            "requirements__asset_types__locations",
            "requirements__qualifying_skills__eve_type",
        )
        .annotate(
            active_member_count=Count(
                "memberships",
                filter=Q(
                    memberships__status=TribeGroupMembership.STATUS_ACTIVE
                ),
            )
        )
    )
    member_group_ids = active_member_group_ids(request.user)
    resolver = ChiefResolver()
    result = [
        serialize_tribe_group(
            tg,
            request_user=request.user,
            member_count=tg.active_member_count,
            member_group_ids=member_group_ids,
            resolver=resolver,
        )
        for tg in groups
    ]
    return 200, result

"""GET /{tribe_id}/groups/{group_id}/activities - configured activity types for a tribe group."""

from authentication import AuthBearer
from ninja import Router

from tribes.endpoints.groups.schemas import (
    TribeGroupActivityDefinitionListSchema,
    TribeGroupActivityDefinitionSchema,
)
from tribes.helpers import user_is_active_tribe_member, user_is_tribe_chief
from tribes.models import Tribe, TribeGroup, TribeGroupActivity

PATH = "/{tribe_id}/groups/{group_id}/activities"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "List activity definitions for a tribe group (what is tracked). "
        "Requires an active tribe membership (any group in the tribe) or tribe chief."
    ),
    "response": {
        200: TribeGroupActivityDefinitionListSchema,
        403: dict,
        404: dict,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Activity"])


def get_tribe_group_activity_definitions(
    request,
    tribe_id: int,
    group_id: int,
):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if not tribe:
        return 404, {"detail": "Tribe not found."}

    group = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .select_related("tribe")
        .first()
    )
    if not group:
        return 404, {"detail": "Tribe group not found."}

    if not (
        user_is_active_tribe_member(request.user, tribe_id)
        or user_is_tribe_chief(request.user, tribe)
    ):
        return 403, {
            "detail": "You must be a member of this tribe to view activities."
        }

    labels = dict(TribeGroupActivity.ACTIVITY_TYPE_CHOICES)
    items = []
    for a in TribeGroupActivity.objects.filter(
        tribe_group_id=group_id
    ).order_by("activity_type", "pk"):
        items.append(
            TribeGroupActivityDefinitionSchema(
                id=a.pk,
                activity_type=a.activity_type,
                activity_type_display=labels.get(
                    a.activity_type, a.activity_type
                ),
                source_eve_type_id=a.source_eve_type_id,
                target_eve_type_id=a.target_eve_type_id,
                description=a.description or "",
                is_active=a.is_active,
                points_per_record=a.points_per_record,
                points_per_unit=a.points_per_unit,
                created_at=a.created_at.isoformat() if a.created_at else "",
                updated_at=a.updated_at.isoformat() if a.updated_at else "",
            )
        )

    return 200, TribeGroupActivityDefinitionListSchema(items=items)


router.get(PATH, **ROUTE_SPEC)(get_tribe_group_activity_definitions)

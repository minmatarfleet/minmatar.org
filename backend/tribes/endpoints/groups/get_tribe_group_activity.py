"""GET "/{tribe_id}/groups/{group_id}/activity" - paginated tribe group activity timeline."""

from ninja import Router, Query

from tribes.endpoints.groups.schemas import (
    TribeGroupActivityListSchema,
    TribeGroupActivityRecordSchema,
)
from tribes.models import (
    TribeGroup,
    TribeGroupActivity,
    TribeGroupActivityRecord,
)

PATH = "/{tribe_id}/groups/{group_id}/activity"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Paginated list of activity records for a tribe group (timeline).",
    "response": {200: TribeGroupActivityListSchema, 404: dict},
}

router = Router(tags=["Tribes - Groups"])

# Max page size for activity list
MAX_LIMIT = 100
DEFAULT_LIMIT = 100


def get_tribe_group_activity(
    request,
    tribe_id: int,
    group_id: int,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    group = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .select_related("tribe")
        .first()
    )
    if not group:
        return 404, {"detail": "Tribe group not found."}

    qs = (
        TribeGroupActivityRecord.objects.filter(
            tribe_group_activity__tribe_group_id=group_id,
            tribe_group_activity__tribe_group__tribe_id=tribe_id,
        )
        .select_related(
            "character",
            "user",
            "tribe_group_activity",
        )
        .order_by("-created_at")
    )
    total = qs.count()
    records = qs[offset : offset + limit]

    activity_type_labels = dict(TribeGroupActivity.ACTIVITY_TYPE_CHOICES)
    items = []
    for r in records:
        activity_type = r.tribe_group_activity.activity_type
        items.append(
            TribeGroupActivityRecordSchema(
                id=r.pk,
                created_at=r.created_at.isoformat() if r.created_at else "",
                activity_type=activity_type,
                activity_type_display=activity_type_labels.get(
                    activity_type, activity_type
                ),
                character_id=(
                    r.character.character_id if r.character else None
                ),
                character_name=(
                    r.character.character_name if r.character else ""
                ),
                user_id=r.user_id,
                username=r.user.username if r.user else "",
                source_type_id=r.source_type_id,
                target_type_id=r.target_type_id,
                quantity=r.quantity,
                unit=r.unit or "",
                reference_type=r.reference_type,
                reference_id=r.reference_id,
            )
        )

    return 200, TribeGroupActivityListSchema(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_group_activity)

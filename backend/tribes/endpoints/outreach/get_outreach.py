"""GET "/{tribe_id}/groups/{group_id}/outreach" - list outreach records for a group."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.outreach.schemas import OutreachSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupOutreach

PATH = "/{tribe_id}/groups/{group_id}/outreach"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List all outreach records for a tribe group (chiefs/elders only).",
    "response": {200: List[OutreachSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Outreach"])


def get_outreach(request, tribe_id: int, group_id: int):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Chiefs and elders only."}

    records = TribeGroupOutreach.objects.filter(tribe_group=tg).select_related(
        "character"
    )
    return 200, [
        OutreachSchema(
            id=r.pk,
            tribe_group_id=tg.pk,
            character_id=r.character.character_id,
            character_name=r.character.character_name,
            sent_by_id=r.sent_by_id,
            sent_at=r.sent_at.isoformat(),
            notes=r.notes,
        )
        for r in records
    ]


router.get(PATH, **ROUTE_SPEC)(get_outreach)

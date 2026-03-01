"""POST "/{tribe_id}/groups/{group_id}/outreach" - record an outreach."""

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.outreach.schemas import (
    OutreachSchema,
    RecordOutreachRequest,
)
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupOutreach
from eveonline.models import EveCharacter

PATH = "/{tribe_id}/groups/{group_id}/outreach"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Record that a chief/elder reached out to a candidate character.",
    "response": {200: OutreachSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Outreach"])


def post_outreach(
    request, tribe_id: int, group_id: int, payload: RecordOutreachRequest
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Chiefs and elders only."}

    character = EveCharacter.objects.filter(
        character_id=payload.character_id
    ).first()
    if not character:
        return 404, {"detail": "Character not found."}

    record, created = TribeGroupOutreach.objects.get_or_create(
        tribe_group=tg,
        character=character,
        defaults={"sent_by": request.user, "notes": payload.notes},
    )
    if not created:
        return 400, {
            "detail": "Outreach already recorded for this character and group."
        }

    return 200, OutreachSchema(
        id=record.pk,
        tribe_group_id=tg.pk,
        character_id=character.character_id,
        character_name=character.character_name,
        sent_by_id=record.sent_by_id,
        sent_at=record.sent_at.isoformat(),
        notes=record.notes,
    )


router.post(PATH, **ROUTE_SPEC)(post_outreach)

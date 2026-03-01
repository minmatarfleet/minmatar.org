"""POST "/{tribe_id}/groups/{group_id}/activities" - manually log an activity."""

from django.contrib.auth import get_user_model

from ninja import Router

from authentication import AuthBearer
from eveonline.models import EveCharacter
from tribes.endpoints.output.schemas import ActivitySchema, LogActivityRequest
from tribes.helpers import user_can_manage_group
from tribes.models import TribeActivity, TribeGroup

user_model = get_user_model()

PATH = "/{tribe_id}/groups/{group_id}/activities"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Manually log an activity entry (chiefs/elders only).",
    "response": {200: ActivitySchema, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Output"])


def post_activity(
    request,
    tribe_id: int,
    group_id: int,
    payload: LogActivityRequest,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Chiefs and elders only."}

    user = user_model.objects.filter(pk=payload.user_id).first()
    if not user:
        return 404, {"detail": "User not found."}

    character = None
    if payload.character_id:
        character = EveCharacter.objects.filter(
            character_id=payload.character_id
        ).first()

    activity = TribeActivity.objects.create(
        tribe_group=tg,
        user=user,
        character=character,
        activity_type=payload.activity_type,
        quantity=payload.quantity,
        unit=payload.unit,
        description=payload.description,
    )
    return 200, ActivitySchema(
        id=activity.pk,
        tribe_group_id=tg.pk,
        tribe_group_name=str(tg),
        user_id=activity.user_id,
        character_id=character.character_id if character else None,
        activity_type=activity.activity_type,
        quantity=activity.quantity,
        unit=activity.unit,
        description=activity.description,
        created_at=activity.created_at.isoformat(),
    )


router.post(PATH, **ROUTE_SPEC)(post_activity)

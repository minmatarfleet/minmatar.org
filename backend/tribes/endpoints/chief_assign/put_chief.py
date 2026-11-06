"""PUT chief of a tribe or a group (superuser swap)."""

from django.contrib.auth.models import User
from ninja import Router

from authentication import AuthBearer
from discord.exceptions import DiscordRoleAssignmentError
from tribes.endpoints.chief_assign.schemas import (
    ChiefSeatSchema,
    SetChiefRequest,
)
from tribes.helpers.chiefs import ChiefVolunteerError, set_chief
from tribes.models import Tribe, TribeGroup

TRIBE_PATH = "/{tribe_id}/chief"
GROUP_PATH = "/{tribe_id}/groups/{group_id}/chief"
RESPONSES = {200: ChiefSeatSchema, 400: dict, 403: dict, 404: dict, 502: dict}
ROUTE_SPEC = {
    "summary": "Swap the chief of a seat, or empty it (superuser only).",
    "response": RESPONSES,
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Chiefs"])


def _apply(request, tribe, tribe_group, payload: SetChiefRequest):
    user = None
    if payload.user_id is not None:
        user = User.objects.filter(pk=payload.user_id).first()
        if user is None:
            return 404, {"detail": "Pilot not found."}
    try:
        set_chief(request.user, tribe, tribe_group, user)
    except ChiefVolunteerError as exc:
        return exc.status_code, {"detail": str(exc)}
    except DiscordRoleAssignmentError:
        return 502, {
            "detail": "Discord didn't give them the group role, so the "
            "chief wasn't changed. Try again in a minute."
        }
    # pylint: disable-next=import-outside-toplevel
    from tribes.endpoints.serialization import user_to_character_ref

    ref = user_to_character_ref(user) if user else None
    return 200, {
        "tribe_id": tribe.pk,
        "tribe_group_id": tribe_group.pk if tribe_group else None,
        "user_id": user.pk if user else None,
        "character_id": ref.character_id if ref else None,
        "character_name": ref.character_name if ref else "",
    }


def put_tribe_chief(request, tribe_id: int, payload: SetChiefRequest):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if tribe is None:
        return 404, {"detail": "Tribe not found."}
    return _apply(request, tribe, None, payload)


def put_group_chief(
    request, tribe_id: int, group_id: int, payload: SetChiefRequest
):
    tribe_group = (
        TribeGroup.objects.select_related("tribe")
        .filter(pk=group_id, tribe_id=tribe_id)
        .first()
    )
    if tribe_group is None:
        return 404, {"detail": "TribeGroup not found."}
    return _apply(request, tribe_group.tribe, tribe_group, payload)


router.put(TRIBE_PATH, **ROUTE_SPEC)(put_tribe_chief)
router.put(GROUP_PATH, **ROUTE_SPEC)(put_group_chief)

"""GET /{tribe_id}/groups/{group_id}/growth — public membership growth."""

from ninja import Router

from tribes.endpoints.groups.schemas import TribeGroupGrowthSchema
from tribes.helpers.growth import group_membership_growth
from tribes.models import TribeGroup

PATH = "/{tribe_id}/groups/{group_id}/growth"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Monthly active member counts for a tribe group.",
    "response": {200: TribeGroupGrowthSchema, 404: dict},
}

router = Router(tags=["Tribes - Groups"])


def get_tribe_group_growth(request, tribe_id: int, group_id: int):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "Tribe group not found."}

    payload = group_membership_growth(tg)
    return 200, TribeGroupGrowthSchema(
        months=payload["months"],
        counts=payload["counts"],
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_group_growth)

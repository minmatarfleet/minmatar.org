"""GET /{tribe_id}/groups/{group_id}/roster — alliance-only public roster."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation
from tribes.endpoints.groups.schemas import TribeGroupRosterEntrySchema
from tribes.helpers import user_is_alliance_member
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/roster"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Active members (primary character only) for a tribe group.",
    "description": (
        "Alliance members and superusers only. No committed alts or "
        "requirement qualification flags."
    ),
    "response": {
        200: List[TribeGroupRosterEntrySchema],
        403: dict,
        404: dict,
    },
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Groups"])


def get_tribe_group_roster(request, tribe_id: int, group_id: int):
    tg = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .select_related("tribe")
        .first()
    )
    if not tg:
        return 404, {"detail": "Tribe group not found."}

    if not user_is_alliance_member(request.user):
        return 403, {"detail": "Alliance members only."}

    memberships = (
        TribeGroupMembership.objects.filter(
            tribe_group=tg,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        .select_related(
            "user__eveplayer__primary_character",
            "rank",
        )
        .order_by("approved_at", "created_at")
    )

    primaries = [user_primary_character(m.user) for m in memberships]
    corp_ids = {
        int(primary.corporation_id)
        for primary in primaries
        if primary is not None and primary.corporation_id is not None
    }
    corp_names = {
        c.corporation_id: c.name
        for c in EveCorporation.objects.filter(corporation_id__in=corp_ids)
    }

    rows: list[TribeGroupRosterEntrySchema] = []
    for membership, primary in zip(memberships, primaries):
        corp_id = (
            int(primary.corporation_id)
            if primary is not None and primary.corporation_id is not None
            else None
        )
        rows.append(
            TribeGroupRosterEntrySchema(
                user_id=membership.user_id,
                primary_character_id=(
                    primary.character_id if primary else None
                ),
                primary_character_name=(
                    (primary.character_name or "") if primary else ""
                ),
                corporation_id=corp_id,
                corporation_name=(
                    corp_names.get(corp_id) if corp_id is not None else None
                ),
                rank_id=membership.rank_id,
                rank_code=membership.rank.code if membership.rank_id else None,
                rank_name=membership.rank.name if membership.rank_id else None,
                rank_sort_order=(
                    membership.rank.sort_order if membership.rank_id else None
                ),
                approved_at=(
                    membership.approved_at.isoformat()
                    if membership.approved_at
                    else None
                ),
            )
        )
    return 200, rows


router.get(PATH, **ROUTE_SPEC)(get_tribe_group_roster)

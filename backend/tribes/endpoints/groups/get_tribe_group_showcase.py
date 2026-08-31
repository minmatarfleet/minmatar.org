"""GET /{tribe_id}/groups/{group_id}/showcase — public totals + alliance names."""

from ninja import Router

from authentication import AuthOptional
from tribes.endpoints.groups.schemas import (
    TribeGroupShowcaseContributorSchema,
    TribeGroupShowcaseSchema,
)
from tribes.helpers import user_is_alliance_member
from tribes.helpers.showcase import build_group_showcase
from tribes.models import TribeGroup
from tribes.reports import ReportError

PATH = "/{tribe_id}/groups/{group_id}/showcase"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Group Activity showcase (30d totals; named rows for alliance).",
    "response": {200: TribeGroupShowcaseSchema, 404: dict},
    "auth": AuthOptional(),
}

router = Router(tags=["Tribes - Groups"])


def get_tribe_group_showcase(request, tribe_id: int, group_id: int):
    tg = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .select_related("tribe")
        .first()
    )
    if not tg:
        return 404, {"detail": "Tribe group not found."}

    try:
        payload = build_group_showcase(tg)
    except ReportError as exc:
        return 404, {"detail": str(exc)}

    include_names = user_is_alliance_member(request.user)
    contributors = []
    if include_names:
        contributors = [
            TribeGroupShowcaseContributorSchema(
                character_id=c.get("character_id"),
                character_name=c.get("character_name") or "",
                metric_key=c.get("metric_key") or "",
                metric_value=c.get("metric_value") or 0,
            )
            for c in payload.get("contributors") or []
        ]

    return 200, TribeGroupShowcaseSchema(
        group_id=payload["group_id"],
        group_code=payload.get("group_code") or "",
        group_name=payload.get("group_name") or "",
        period=payload.get("period") or "",
        period_start=payload.get("period_start"),
        period_end=payload.get("period_end"),
        manual=bool(payload.get("manual")),
        message=payload.get("message") or "",
        totals=payload.get("totals") or {},
        columns=payload.get("columns") or [],
        contributors=contributors,
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_group_showcase)

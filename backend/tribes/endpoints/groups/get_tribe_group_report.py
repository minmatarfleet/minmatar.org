"""GET /{tribe_id}/groups/{group_id}/reports/{view} — tribe group report."""

from ninja import Router, Query

from tribes.endpoints.groups.schemas import TribeGroupReportSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup
from tribes.reports import ReportError, run_group_report
from tribes.reports.types import ReportView

PATH = "/{tribe_id}/groups/{group_id}/reports/{view}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Town hall or member report for a tribe group.",
    "response": {200: TribeGroupReportSchema, 403: dict, 404: dict},
}

router = Router(tags=["Tribes - Groups"])


def get_tribe_group_report(
    request,
    tribe_id: int,
    group_id: int,
    view: str,
    period: str = Query("30d"),
    scope: str | None = Query(None),
):
    group = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .select_related("tribe")
        .first()
    )
    if not group:
        return 404, {"detail": "Tribe group not found."}

    if view not in {v.value for v in ReportView}:
        return 404, {"detail": "Invalid report view."}

    if not user_can_manage_group(request.user, group):
        return 403, {"detail": "Permission denied."}

    try:
        result = run_group_report(group, view=view, period=period, scope=scope)
    except ReportError as exc:
        return 404, {"detail": str(exc)}

    return 200, TribeGroupReportSchema(
        group_id=result.group_id,
        group_code=result.group_code,
        group_name=result.group_name,
        view=result.view,
        scope=result.scope,
        period=result.period,
        period_start=result.period_start.isoformat(),
        period_end=result.period_end.isoformat(),
        generated_at=result.generated_at.isoformat(),
        manual=result.manual,
        message=result.message,
        columns=result.columns,
        rows=result.rows,
        totals=result.totals,
    )


router.get(PATH, **ROUTE_SPEC)(get_tribe_group_report)

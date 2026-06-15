"""Execute tribe group reports from registry bindings."""

from datetime import datetime

from django.utils import timezone

from tribes.models import TribeGroup
from tribes.reports.period import parse_period
from tribes.reports.registry import (
    QUERY_RUNNERS,
    REPORT_BINDINGS,
    binding_for_group,
)
from tribes.reports.types import ReportResult, ReportView


class ReportError(Exception):
    pass


def run_group_report(
    tribe_group: TribeGroup,
    *,
    view: str = ReportView.TOWN_HALL.value,
    period: str = "30d",
) -> ReportResult:
    binding = binding_for_group(tribe_group)
    if not binding:
        raise ReportError(
            f"No report binding for group code {tribe_group.code!r}"
        )
    return _run_binding(
        tribe_group,
        binding,
        view=view,
        period=period,
    )


def run_report_by_code(
    code: str,
    *,
    view: str = ReportView.TOWN_HALL.value,
    period: str = "30d",
) -> ReportResult:
    tribe_group = TribeGroup.objects.filter(code=code, is_active=True).first()
    if not tribe_group:
        raise ReportError(f"TribeGroup with code {code!r} not found")
    return run_group_report(tribe_group, view=view, period=period)


def _run_binding(
    tribe_group, binding, *, view: str, period: str
) -> ReportResult:
    now = timezone.now()
    bounds = parse_period(period)
    period_start = timezone.make_aware(
        datetime.combine(bounds.start, datetime.min.time())
    )
    period_end = timezone.make_aware(
        datetime.combine(bounds.end, datetime.max.time())
    )

    if binding.manual:
        return ReportResult(
            group_id=tribe_group.pk,
            group_code=binding.code,
            group_name=tribe_group.name,
            view=view,
            scope="manual",
            period=bounds.label,
            period_start=period_start,
            period_end=period_end,
            generated_at=now,
            manual=True,
            message=binding.manual_message,
        )

    spec = binding.views.get(view)
    if not spec:
        raise ReportError(f"No view {view!r} configured for {binding.code}")

    runner = QUERY_RUNNERS.get(spec.query_key)
    if not runner:
        raise ReportError(f"Unknown query key: {spec.query_key}")

    rows, totals, columns = runner(
        tribe_group, bounds, spec.scope, spec.params
    )

    pres = binding.presentation.get(view, {})
    top_n = pres.get("top_n")
    if top_n and rows:
        sort_key = pres.get("sort")
        if sort_key:
            rows.sort(key=lambda r: r.get(sort_key, 0), reverse=True)
        rows = rows[:top_n]

    return ReportResult(
        group_id=tribe_group.pk,
        group_code=binding.code,
        group_name=tribe_group.name,
        view=view,
        scope=spec.scope.value,
        period=bounds.label,
        period_start=period_start,
        period_end=period_end,
        generated_at=now,
        columns=columns,
        rows=rows,
        totals=totals,
    )


def all_reportable_groups():
    """Active groups that have a registry binding."""
    codes = {
        code for code, binding in REPORT_BINDINGS.items() if not binding.manual
    }
    return TribeGroup.objects.filter(is_active=True, code__in=codes).order_by(
        "tribe__name", "name"
    )

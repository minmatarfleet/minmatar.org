"""GET history — counts, ISK totals, and breakdowns by ship group and type."""

from datetime import timedelta
from typing import Literal

from django.db.models import Count, Min, Q, Sum
from django.utils import timezone
from app.errors import ErrorResponse
from authentication import AuthBearer
from onboarding.srp_gate import require_current_srp_onboarding
from eveuniverse.models import EveType
from pydantic import BaseModel
from srp.models import EveFleetShipReimbursement

PATH = "history"
METHOD = "get"

_HISTORY_DAY_CHOICES = frozenset({"30", "90", "180", "365", "all"})


class RequestsBreakdown(BaseModel):
    total: int
    approved: int
    rejected: int


class AmountsBreakdown(BaseModel):
    total: int
    approved: int
    rejected: int


class GroupStat(BaseModel):
    group_name: str
    group_id: int
    total: int
    approved: int
    rejected: int


class TypeStat(BaseModel):
    type_name: str
    type_id: int
    total: int
    approved: int
    rejected: int


class SrpStatsHistoryResponse(BaseModel):
    requests: RequestsBreakdown
    amounts: AmountsBreakdown
    groups: list[GroupStat]
    types: list[TypeStat]


ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: SrpStatsHistoryResponse,
        403: ErrorResponse,
        400: ErrorResponse,
    },
}


def _history_queryset(days: Literal["30", "90", "180", "365", "all"]):
    qs = EveFleetShipReimbursement.objects.all()
    if days == "all":
        return qs
    n = int(days)
    cutoff = timezone.now() - timedelta(days=n)
    return qs.filter(created_at__gte=cutoff)


def _i(v) -> int:
    return int(v or 0)


def get_srp_stats_history(request, days: str = "90"):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }

    denied = require_current_srp_onboarding(request)
    if denied:
        return denied

    if days not in _HISTORY_DAY_CHOICES:
        return 400, {
            "detail": "Invalid days; use one of: 30, 90, 180, 365, all",
        }

    qs = _history_queryset(days)  # type: ignore[arg-type]

    agg = qs.aggregate(
        total_req=Count("id"),
        approved_req=Count("id", filter=Q(status="approved")),
        rejected_req=Count("id", filter=Q(status="rejected")),
        total_amt=Sum("amount"),
        approved_amt=Sum("amount", filter=Q(status="approved")),
        rejected_amt=Sum("amount", filter=Q(status="rejected")),
    )

    requests = RequestsBreakdown(
        total=_i(agg["total_req"]),
        approved=_i(agg["approved_req"]),
        rejected=_i(agg["rejected_req"]),
    )
    amounts = AmountsBreakdown(
        total=_i(agg["total_amt"]),
        approved=_i(agg["approved_amt"]),
        rejected=_i(agg["rejected_amt"]),
    )

    type_rows = (
        qs.values("ship_type_id")
        .annotate(
            total=Sum("amount"),
            approved=Sum("amount", filter=Q(status="approved")),
            rejected=Sum("amount", filter=Q(status="rejected")),
        )
        .order_by()
    )

    name_by_type = dict(
        qs.values("ship_type_id")
        .annotate(sample_name=Min("ship_name"))
        .values_list("ship_type_id", "sample_name")
    )

    type_ids = {row["ship_type_id"] for row in type_rows}
    type_meta: dict[int, tuple[int, str, str]] = {}
    if type_ids:
        for et in EveType.objects.filter(id__in=type_ids).select_related(
            "eve_group"
        ):
            gid = et.eve_group_id if et.eve_group_id is not None else 0
            gname = et.eve_group.name if et.eve_group_id else "Unknown"
            type_meta[et.id] = (gid, gname, et.name)

    types_out: list[TypeStat] = []
    group_acc: dict[int, tuple[str, int, int, int]] = {}

    for row in type_rows:
        tid = row["ship_type_id"]
        t_total = _i(row["total"])
        t_appr = _i(row["approved"])
        t_rej = _i(row["rejected"])
        meta = type_meta.get(tid)
        if meta:
            gid, gname, tname = meta
        else:
            gid, gname = 0, "Unknown"
            tname = name_by_type.get(tid) or "Unknown"
        types_out.append(
            TypeStat(
                type_name=tname,
                type_id=int(tid),
                total=t_total,
                approved=t_appr,
                rejected=t_rej,
            )
        )
        prev = group_acc.get(gid)
        if prev:
            gname_p, a, b, c = prev
            group_acc[gid] = (gname_p, a + t_total, b + t_appr, c + t_rej)
        else:
            group_acc[gid] = (gname, t_total, t_appr, t_rej)

    types_out.sort(key=lambda x: x.total, reverse=True)
    groups_out = [
        GroupStat(
            group_name=name,
            group_id=gid,
            total=tot,
            approved=appr,
            rejected=rej,
        )
        for gid, (name, tot, appr, rej) in sorted(
            group_acc.items(), key=lambda kv: kv[1][1], reverse=True
        )
    ]

    return SrpStatsHistoryResponse(
        requests=requests,
        amounts=amounts,
        groups=groups_out,
        types=types_out,
    )

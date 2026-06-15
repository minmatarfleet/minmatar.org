"""Freight program aggregate stats (FL33T freight corp contracts)."""

from datetime import datetime
from statistics import median

from django.utils import timezone

from freight.models import FreightContract
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = []


def run_freight_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    start_dt = timezone.make_aware(
        datetime.combine(period.start, datetime.min.time())
    )
    end_dt = timezone.make_aware(
        datetime.combine(period.end, datetime.max.time())
    )

    contracts = list(
        FreightContract.objects.finished().filter(
            date_completed__gte=start_dt,
            date_completed__lte=end_dt,
        )
    )

    if not contracts:
        return [], _empty_totals(), COLUMNS

    completion_hours = []
    accept_to_complete_hours = []
    total_reward = 0.0
    total_volume = 0.0

    for c in contracts:
        reward = float(c.reward or 0)
        volume = float(c.volume or 0)
        total_reward += reward
        total_volume += volume
        if c.date_issued and c.date_completed:
            delta = c.date_completed - c.date_issued
            completion_hours.append(delta.total_seconds() / 3600.0)
        if c.date_accepted and c.date_completed:
            delta = c.date_completed - c.date_accepted
            accept_to_complete_hours.append(delta.total_seconds() / 3600.0)

    def stats(hours_list):
        if not hours_list:
            return {"avg": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
        return {
            "avg": round(sum(hours_list) / len(hours_list), 1),
            "median": round(median(hours_list), 1),
            "min": round(min(hours_list), 1),
            "max": round(max(hours_list), 1),
        }

    completion = stats(completion_hours)
    accept_complete = stats(accept_to_complete_hours)

    totals = {
        "contracts_completed": len(contracts),
        "total_isk_rewards": round(total_reward, 2),
        "total_volume_m3": round(total_volume, 2),
        "avg_completion_hours": completion["avg"],
        "median_completion_hours": completion["median"],
        "fastest_completion_hours": completion["min"],
        "slowest_completion_hours": completion["max"],
        "avg_accept_to_complete_hours": accept_complete["avg"],
    }
    return [], totals, COLUMNS


def _empty_totals():
    return {
        "contracts_completed": 0,
        "total_isk_rewards": 0.0,
        "total_volume_m3": 0.0,
        "avg_completion_hours": 0.0,
        "median_completion_hours": 0.0,
        "fastest_completion_hours": 0.0,
        "slowest_completion_hours": 0.0,
        "avg_accept_to_complete_hours": 0.0,
    }

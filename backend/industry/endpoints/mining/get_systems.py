"""GET "" - list mining systems (from sovereignty view + computed power/workforce + completions)."""

from datetime import timedelta
from typing import List

from industry.endpoints.mining.schemas import (
    MINING_LEVEL_DURATION_MINUTES,
    MiningCompletionRecord,
    MiningSystemResponse,
)
from industry.models import MiningUpgradeCompletion
from sovereignty.services import (
    get_computed_power_workforce,
    get_mining_level_for_system,
    get_mining_systems_queryset,
)

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List mining systems (sovereignty view) with power, workforce, timer and history",
    "response": {200: List[MiningSystemResponse]},
}


def get_systems(request):
    systems_qs = get_mining_systems_queryset()
    result: List[MiningSystemResponse] = []
    for config in systems_qs:
        system_id = config.system_id
        system_name = config.system_name or str(system_id)
        level = get_mining_level_for_system(system_id)
        if level is None:
            continue
        power, workforce, _, _ = get_computed_power_workforce(system_id)
        completions_qs = (
            MiningUpgradeCompletion.objects.filter(system_id=system_id)
            .select_related("completed_by")
            .order_by("-completed_at")[:50]
        )
        completions_list = list(completions_qs)
        last_completion = (
            completions_list[0].completed_at if completions_list else None
        )
        next_available_at = None
        if last_completion and level in MINING_LEVEL_DURATION_MINUTES:
            duration_min = MINING_LEVEL_DURATION_MINUTES[level]
            next_available_at = last_completion + timedelta(
                minutes=duration_min
            )
        result.append(
            MiningSystemResponse(
                system_id=system_id,
                system_name=system_name,
                mining_upgrade_level=level,
                power=power,
                workforce=workforce,
                last_completion=last_completion,
                next_available_at=next_available_at,
                completions=[
                    MiningCompletionRecord(
                        completed_at=c.completed_at,
                        completed_by_username=(
                            c.completed_by.username if c.completed_by else None
                        ),
                    )
                    for c in completions_list
                ],
            )
        )
    return result

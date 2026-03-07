"""GET "" - list mining systems with upgrades (type_id for icons) and completions (respawn time)."""

from datetime import timedelta
from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.mining.schemas import (
    MINING_LEVEL_DURATION_MINUTES,
    MiningCompletionRecord,
    MiningSystemResponse,
    MiningUpgradeDetail,
)
from industry.models import MiningUpgradeCompletion
from sovereignty.services import (
    get_computed_power_workforce,
    get_mining_level_for_system,
    get_mining_systems_queryset,
)
from sovereignty.upgrade_stats import get_upgrade_stats

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List mining systems with upgrade details (type_id for icons) and completions (respawn)",
    "auth": AuthBearer(),
    "response": {
        200: List[MiningSystemResponse],
        403: ErrorResponse,
    },
}


def _completion_record(c) -> MiningCompletionRecord:
    respawn_min = c.get_respawn_minutes()
    return MiningCompletionRecord(
        completed_at=c.completed_at,
        completed_by_username=(
            c.completed_by.username if c.completed_by else None
        ),
        site_name=c.site_name or "",
        respawn_minutes=respawn_min,
        next_available_at=(
            c.completed_at + timedelta(minutes=respawn_min)
            if respawn_min is not None
            else None
        ),
    )


def get_systems(request):
    if not request.user.has_perm("industry.view_miningupgradecompletion"):
        return 403, ErrorResponse(
            detail="You do not have permission to view mining completions."
        )
    systems_qs = get_mining_systems_queryset()
    result: List[MiningSystemResponse] = []
    for config in systems_qs.prefetch_related("installed_upgrades__eve_type"):
        system_id = config.system_id
        system_name = config.system_name or str(system_id)
        level = get_mining_level_for_system(system_id)
        if level is None:
            continue
        power, workforce, _, _ = get_computed_power_workforce(system_id)

        mining_upgrades: List[MiningUpgradeDetail] = []
        for inst in config.installed_upgrades.all():
            stats = get_upgrade_stats(inst.eve_type)
            if stats.mining_upgrade_level in (1, 2, 3):
                mining_upgrades.append(
                    MiningUpgradeDetail(
                        type_id=inst.eve_type.id,
                        name=inst.eve_type.name or "",
                    )
                )

        completions_qs = (
            MiningUpgradeCompletion.objects.filter(sov_system=config)
            .select_related("completed_by", "sov_system")
            .order_by("-completed_at")[:50]
        )
        completions_list = list(completions_qs)
        last_completion = (
            completions_list[0].completed_at if completions_list else None
        )
        next_available_at = None
        if completions_list:
            first = completions_list[0]
            respawn_min = first.get_respawn_minutes()
            if respawn_min is None:
                respawn_min = MINING_LEVEL_DURATION_MINUTES.get(level, 60)
            next_available_at = first.completed_at + timedelta(
                minutes=respawn_min
            )

        result.append(
            MiningSystemResponse(
                system_id=system_id,
                system_name=system_name,
                mining_upgrade_level=level,
                mining_upgrades=mining_upgrades,
                power=power,
                workforce=workforce,
                last_completion=last_completion,
                next_available_at=next_available_at,
                completions=[_completion_record(c) for c in completions_list],
            )
        )
    return result

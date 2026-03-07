"""
Sovereignty services: computed power/workforce and mining systems view.
"""

from typing import Optional

from django.db.models import QuerySet

from sovereignty.models import (
    SystemBaseResources,
    SystemSovereigntyConfig,
    SystemSovereigntyUpgrade,
)


def get_base_power_workforce(system_id: int) -> tuple[int, int]:
    """Return (base_power, base_workforce) for a system from cache or 0,0."""
    try:
        row = SystemBaseResources.objects.get(system_id=system_id)
        return row.base_power, row.base_workforce
    except SystemBaseResources.DoesNotExist:
        return 0, 0


def get_computed_power_workforce(
    system_id: int,
) -> tuple[int, int, Optional[int], Optional[int]]:
    """
    Compute power and workforce for a system: base (SDE/cache) minus upgrade costs plus conversion.

    Returns (power, workforce, base_power, base_workforce).
    """
    base_power, base_workforce = get_base_power_workforce(system_id)
    power = base_power
    workforce = base_workforce

    try:
        config = SystemSovereigntyConfig.objects.get(system_id=system_id)
    except SystemSovereigntyConfig.DoesNotExist:
        return power, workforce, base_power, base_workforce

    upgrades = SystemSovereigntyUpgrade.objects.filter(
        system=config
    ).select_related("upgrade_type")
    for inst in upgrades:
        t = inst.upgrade_type
        power -= t.power_cost or 0
        workforce -= t.workforce_cost or 0
        if t.produces_power and t.consumes_workforce:
            power += t.produces_power
            workforce -= t.consumes_workforce
        if t.produces_workforce and t.consumes_power:
            workforce += t.produces_workforce
            power -= t.consumes_power

    return max(0, power), max(0, workforce), base_power, base_workforce


def get_mining_systems_queryset() -> QuerySet[SystemSovereigntyConfig]:
    """
    Systems that have at least one installed upgrade with mining_upgrade_level in (1, 2, 3).
    """
    return SystemSovereigntyConfig.objects.filter(
        installed_upgrades__upgrade_type__mining_upgrade_level__in=[1, 2, 3]
    ).distinct()


def get_mining_level_for_system(system_id: int) -> Optional[int]:
    """
    Return the mining upgrade level (1, 2, or 3) for the system, or None if not a mining system.
    Uses max of installed mining upgrade levels if multiple.
    """
    levels = (
        SystemSovereigntyUpgrade.objects.filter(system__system_id=system_id)
        .filter(upgrade_type__mining_upgrade_level__in=[1, 2, 3])
        .values_list("upgrade_type__mining_upgrade_level", flat=True)
    )
    return max(levels) if levels else None

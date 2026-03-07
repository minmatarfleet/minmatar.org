"""
Sovereignty services: register systems, computed power/workforce, mining view, anomalies.
"""

from typing import Optional

from django.db.models import QuerySet
from eveuniverse.models import EveSolarSystem

from sovereignty.anomalies import get_anomalies_for_upgrades
from sovereignty.models import (
    SystemBaseResources,
    SystemSovereigntyConfig,
    SystemSovereigntyUpgrade,
)
from sovereignty.upgrade_stats import get_upgrade_stats


# Default base power/workforce when registering a system (typical nullsec star ~650 power).
DEFAULT_BASE_POWER = 650
DEFAULT_BASE_WORKFORCE = 0


def register_system(
    system_id: int,
    *,
    base_power: Optional[int] = None,
    base_workforce: Optional[int] = None,
) -> tuple[SystemSovereigntyConfig, SystemBaseResources]:
    """
    Register a system for sovereignty tracking. Resolves name from Eve universe (EveSolarSystem)
    and creates/updates base resources. Returns (config, base_resources).
    """
    solar_system, _ = EveSolarSystem.objects.get_or_create_esi(id=system_id)
    config, _ = SystemSovereigntyConfig.objects.update_or_create(
        system_id=system_id,
        defaults={"system_name": solar_system.name or ""},
    )
    base_resources, _ = SystemBaseResources.objects.update_or_create(
        system_id=system_id,
        defaults={
            "base_power": (
                base_power if base_power is not None else DEFAULT_BASE_POWER
            ),
            "base_workforce": (
                base_workforce
                if base_workforce is not None
                else DEFAULT_BASE_WORKFORCE
            ),
        },
    )
    return config, base_resources


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
    Compute power and workforce for a system: base (from universe/cache) minus upgrade costs
    plus conversion. Stats are derived from each installed EveType via eveuniverse dogma.

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
    ).select_related("eve_type")
    for inst in upgrades:
        stats = get_upgrade_stats(inst.eve_type)
        # Allocation (cost). Conversion upgrades: workforce producer consumes power (not power_cost again); power producer consumes workforce.
        if stats.produces_workforce and stats.consumes_power:
            workforce += stats.produces_workforce
            power -= stats.consumes_power
            workforce -= stats.workforce_cost or 0
        else:
            power -= stats.power_cost or 0
            workforce -= stats.workforce_cost or 0
        if stats.produces_power and stats.consumes_workforce:
            power += stats.produces_power
            workforce -= stats.consumes_workforce

    return max(0, power), max(0, workforce), base_power, base_workforce


def get_mining_systems_queryset() -> QuerySet[SystemSovereigntyConfig]:
    """
    Systems that have at least one installed upgrade with mining_upgrade_level in (1, 2, 3).
    Mining level is derived from EveType (eveuniverse) by name/dogma.
    """
    configs_with_upgrades = SystemSovereigntyConfig.objects.filter(
        installed_upgrades__isnull=False
    ).distinct()
    # Filter to those where at least one upgrade has mining level 1, 2, or 3
    result = []
    for config in configs_with_upgrades:
        upgrades = config.installed_upgrades.select_related("eve_type").all()
        for inst in upgrades:
            stats = get_upgrade_stats(inst.eve_type)
            if stats.mining_upgrade_level in (1, 2, 3):
                result.append(config.pk)
                break
    return SystemSovereigntyConfig.objects.filter(pk__in=result)


def get_mining_level_for_system(system_id: int) -> Optional[int]:
    """
    Return the mining upgrade level (1, 2, or 3) for the system, or None if not a mining system.
    Uses max of installed upgrade levels (derived from EveType) if multiple.
    """
    levels = []
    for inst in SystemSovereigntyUpgrade.objects.filter(
        system__system_id=system_id
    ).select_related("eve_type"):
        stats = get_upgrade_stats(inst.eve_type)
        if stats.mining_upgrade_level in (1, 2, 3):
            levels.append(stats.mining_upgrade_level)
    return max(levels) if levels else None


def get_anomalies_for_system(system_id: int) -> list[tuple[str, int]]:
    """
    Return anomalies generated by the system's sovereignty upgrades, given its security band.
    Matches spreadsheet listAnomsInSystem: (anomaly_name, qty) list.
    """
    try:
        config = SystemSovereigntyConfig.objects.get(system_id=system_id)
    except SystemSovereigntyConfig.DoesNotExist:
        return []

    try:
        solar_system = EveSolarSystem.objects.get(id=system_id)
        security_status = float(solar_system.security_status)
    except (EveSolarSystem.DoesNotExist, (TypeError, ValueError)):
        security_status = -0.5

    upgrade_names = list(
        config.installed_upgrades.select_related("eve_type")
        .values_list("eve_type__name", flat=True)
        .filter(eve_type__name__isnull=False)
    )
    return get_anomalies_for_upgrades(upgrade_names, security_status)

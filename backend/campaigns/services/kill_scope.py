"""Where a campaign's kills count.

By default a kill counts in an FW objective system, or in a system holding
a campaign structure (the structure-bash path). A campaign with the
Destruction feature counts every kill in its whole area: any campaign
system, any system inside a constellation or region area, and any system
with a campaign structure.
"""

from __future__ import annotations

from campaigns.models import Campaign
from campaigns.services.areas import systems_in_area
from eveuniverse.models import EveSolarSystem
from feed.models import FeedMonitoredSystem


def area_system_ids(campaign: Campaign) -> set[int]:
    ids: set[int] = set()
    for area in campaign.areas.all():
        ids |= systems_in_area(area)
    return ids


def in_area(campaign: Campaign, solar_system_id: int) -> bool:
    return any(
        solar_system_id in systems_in_area(area)
        for area in campaign.areas.all()
    )


def kill_scope_system_ids(campaign: Campaign) -> set[int]:
    """Every system a kill counts in for this campaign."""
    ids = set(campaign.system_ids())
    ids |= set(campaign.structures.values_list("solar_system_id", flat=True))
    if campaign.destruction_enabled:
        ids |= area_system_ids(campaign)
    return ids


def monitor_kill_scope(campaign: Campaign) -> int:
    """Have the feed keep mails for every system in a Destruction
    campaign's area. Returns how many systems were added."""
    if not campaign.destruction_enabled:
        return 0
    wanted = kill_scope_system_ids(campaign)
    known = set(
        FeedMonitoredSystem.objects.filter(
            solar_system_id__in=wanted
        ).values_list("solar_system_id", flat=True)
    )
    missing = wanted - known
    if not missing:
        return 0
    names = dict(
        EveSolarSystem.objects.filter(id__in=missing).values_list("id", "name")
    )
    FeedMonitoredSystem.objects.bulk_create(
        [
            FeedMonitoredSystem(
                solar_system_id=system_id,
                name=names.get(system_id) or str(system_id),
                source=FeedMonitoredSystem.Source.CAMPAIGN,
                is_active=True,
            )
            for system_id in sorted(missing)
        ],
        ignore_conflicts=True,
    )
    return len(missing)

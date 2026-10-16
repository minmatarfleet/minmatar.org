"""
Who fills each fleet role, worked out from ships instead of sign-ups.

Two sources, one row per pilot:

- A ship volunteer brings that fit, running the bursts they picked.
- A pilot in the tracked fleet is matched to the composition fit for the
  hull they are flying (first by role order) and assumed to run its online
  bursts. What they are actually in wins over what they volunteered; if the
  hulls agree, their volunteered bursts are kept.

Logi FC is the exception: it is a person, so it stays a sign-up.
"""

from dataclasses import dataclass
from datetime import timedelta

from eveuniverse.models import EveType

from fleets.helpers.composition import fleet_composition
from fleets.helpers.fit_roles import (
    BURST_KINDS,
    BURST_LABELS,
    FitRoles,
    LOGI_HULL_GROUPS,
)

# The poller rewrites every present member and then stamps the instance;
# a member not touched on the latest pass has left.
PRESENT_SLACK = timedelta(minutes=5)


@dataclass
class RolePilot:
    character_id: int
    character_name: str
    ship_id: int
    ship_name: str
    fitting_name: str
    source: str  # volunteer | in_fleet
    in_fleet: bool
    roles: FitRoles
    bursts: list
    ship_volunteer_id: int | None = None
    solar_system_id: int | None = None
    solar_system_name: str = ""


def _present_members(fleet, visible):
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance, EveFleetInstanceMember

    instance = (
        EveFleetInstance.objects.filter(eve_fleet=fleet, end_time__isnull=True)
        .order_by("-start_time")
        .first()
    )
    if not instance or not instance.last_updated:
        return []
    members = EveFleetInstanceMember.objects.filter(
        eve_fleet_instance=instance,
        updated_at__gte=instance.last_updated - PRESENT_SLACK,
    )
    return [m for m in members if visible(m.character_id)]


def fleet_role_pilots(fleet, visible=lambda character_id: True):
    """Every pilot whose ship fills a role, volunteered or in fleet."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetShipVolunteer

    entries = fleet_composition(fleet)
    by_key = {entry.key: entry for entry in entries}
    by_hull = {}
    for entry in entries:
        by_hull.setdefault(entry.ship_id, entry)

    pilots: dict[int, RolePilot] = {}
    for volunteer in EveFleetShipVolunteer.objects.filter(
        eve_fleet=fleet
    ).order_by("id"):
        if not visible(volunteer.character_id):
            continue
        key = (
            f"f:{volunteer.fitting_id}"
            if volunteer.fitting_id
            else f"m:{volunteer.fleet_fitting_id}"
        )
        entry = by_key.get(key)
        if entry is None:
            continue  # fit dropped from the composition since
        pilots[volunteer.character_id] = RolePilot(
            character_id=volunteer.character_id,
            character_name=volunteer.character_name,
            ship_id=entry.ship_id,
            ship_name=entry.ship_name,
            fitting_name=entry.name,
            source="volunteer",
            in_fleet=False,
            roles=entry.roles,
            bursts=list(volunteer.bursts or []),
            ship_volunteer_id=volunteer.id,
            solar_system_id=volunteer.solar_system_id,
            solar_system_name=volunteer.solar_system_name,
        )

    members = _present_members(fleet, visible)
    hull_groups = dict(
        EveType.objects.filter(
            id__in={m.ship_type_id for m in members}
        ).values_list("id", "eve_group__name")
    )
    for member in members:
        planned = pilots.get(member.character_id)
        if planned and planned.ship_id == member.ship_type_id:
            planned.in_fleet = True
            continue
        entry = by_hull.get(member.ship_type_id)
        if entry is not None:
            roles, fitting_name = entry.roles, entry.name
            bursts = roles.default_bursts()
        else:
            # Off-doctrine hull: only logi can be told from the hull alone.
            roles = FitRoles(
                logi=hull_groups.get(member.ship_type_id) in LOGI_HULL_GROUPS
            )
            fitting_name, bursts = "", []
        pilots[member.character_id] = RolePilot(
            character_id=member.character_id,
            character_name=member.character_name,
            ship_id=member.ship_type_id,
            ship_name=member.ship_name,
            fitting_name=fitting_name,
            source="in_fleet",
            in_fleet=True,
            roles=roles,
            bursts=bursts,
        )
    return list(pilots.values())


def fleet_role_coverage(fleet, visible=lambda character_id: True) -> dict:
    """Links by kind, cynos and logi, from ``fleet_role_pilots``."""
    pilots = fleet_role_pilots(fleet, visible)
    links = []
    for kind in BURST_KINDS:
        running = [
            (pilot, pilot.bursts.count(kind))
            for pilot in pilots
            if kind in pilot.bursts
        ]
        # Mining links only show up when someone actually brings them.
        if kind == "mining" and not running:
            continue
        links.append(
            {"kind": kind, "label": BURST_LABELS[kind], "pilots": running}
        )
    return {
        "links": links,
        "cynos": [pilot for pilot in pilots if pilot.roles.cyno],
        "logi": [pilot for pilot in pilots if pilot.roles.logi],
    }

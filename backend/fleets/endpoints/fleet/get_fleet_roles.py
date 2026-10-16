"""GET /{fleet_id}/roles — who fills links, cynos and logi, from ships."""

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters

from fleets.endpoints.helpers import (
    _fleet_authorized,
    _system_reveal_predicate,
    is_strategic_fc,
    make_role_volunteer_response,
)
from fleets.endpoints.schemas import (
    EveFleetLinkCoverage,
    EveFleetRoleCoverageResponse,
    EveFleetRolePilot,
)
from fleets.helpers.role_coverage import fleet_role_coverage
from fleets.models import EveFleet, EveFleetRoleVolunteer

PATH = "/{fleet_id}/roles"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: EveFleetRoleCoverageResponse, 403: None, 404: None},
    "description": (
        "Fleet roles worked out from ships: links by burst kind, cynos and "
        "logi, from ship volunteers and pilots in the tracked fleet. Logi FC "
        "is the one role still signed up for. A hidden roster limits "
        "everyone but a Strategic FC to their own characters; a cyno system "
        "is only returned to the FC and the pilot."
    ),
}


def _pilot_response(pilot, reveal, count: int = 0) -> EveFleetRolePilot:
    show = pilot.ship_volunteer_id is not None and reveal(pilot)
    return EveFleetRolePilot(
        character_id=pilot.character_id,
        character_name=pilot.character_name,
        ship_id=pilot.ship_id,
        ship_name=pilot.ship_name,
        fitting_name=pilot.fitting_name,
        source=pilot.source,
        in_fleet=pilot.in_fleet,
        count=count,
        ship_volunteer_id=pilot.ship_volunteer_id,
        solar_system_id=pilot.solar_system_id if show else None,
        solar_system_name=(pilot.solar_system_name or None) if show else None,
    )


def get_fleet_roles(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None

    own_ids = {c.character_id for c in user_characters(request.user)}
    see_all = not fleet.hide_volunteers or is_strategic_fc(request.user)

    def visible(character_id):
        return see_all or character_id in own_ids

    coverage = fleet_role_coverage(fleet, visible)
    reveal = _system_reveal_predicate(request, fleet)
    logi_fc = [
        make_role_volunteer_response(v)
        for v in EveFleetRoleVolunteer.objects.filter(
            eve_fleet=fleet, role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR
        ).order_by("id")
        if visible(v.character_id)
    ]
    return EveFleetRoleCoverageResponse(
        logi_fc=logi_fc,
        links=[
            EveFleetLinkCoverage(
                kind=row["kind"],
                label=row["label"],
                pilots=[
                    _pilot_response(pilot, reveal, count)
                    for pilot, count in row["pilots"]
                ],
            )
            for row in coverage["links"]
        ],
        cynos=[_pilot_response(p, reveal) for p in coverage["cynos"]],
        logi=[_pilot_response(p, reveal) for p in coverage["logi"]],
    )

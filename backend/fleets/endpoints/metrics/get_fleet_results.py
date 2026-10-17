"""GET /results — stored kill totals for a set of finished fleets."""

from typing import List

from authentication import AuthBearer
from feed.helpers.fleet_kills import stored_killmail_rows, summary_totals
from feed.models import FeedEventFleetLink

from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import EveFleetResultResponse
from fleets.models import EveFleet, EveFleetInstance

PATH = "/results"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetResultResponse]},
    "description": (
        "ISK and ships destroyed and lost per fleet, read from the stored "
        "fleet_kills cards only. Fleets without a stored card are left out, "
        "so this never matches killmails live. fleet_ids is a comma-separated "
        "list of up to 100 ids."
    ),
}

MAX_FLEETS = 100


def get_fleet_results(request, fleet_ids: str = ""):
    ids = [
        int(part)
        for part in (p.strip() for p in fleet_ids.split(","))
        if part.isdigit()
    ][:MAX_FLEETS]
    if not ids:
        return []

    fleets = [
        fleet
        for fleet in EveFleet.objects.filter(id__in=ids).select_related(
            "audience"
        )
        if _fleet_authorized(request, fleet)
    ]
    fleet_of_instance = dict(
        EveFleetInstance.objects.filter(eve_fleet__in=fleets).values_list(
            "id", "eve_fleet_id"
        )
    )
    rows_by_fleet: dict[int, dict[int, dict]] = {}
    for link in FeedEventFleetLink.objects.filter(
        fleet_instance_id__in=fleet_of_instance.keys(),
        feed_event__rollup_code="fleet_kills",
    ).select_related("feed_event"):
        rows = rows_by_fleet.setdefault(
            fleet_of_instance[link.fleet_instance_id], {}
        )
        rows.update(stored_killmail_rows(link.feed_event))

    return [
        EveFleetResultResponse(
            fleet_id=fleet_id, **summary_totals(list(rows.values()))
        )
        for fleet_id, rows in rows_by_fleet.items()
    ]

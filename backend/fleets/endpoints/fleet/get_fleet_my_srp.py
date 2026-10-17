"""GET /{fleet_id}/my-srp — the caller's losses in this fleet that SRP covers."""

from typing import List

from authentication import AuthBearer
from eveonline.helpers.characters import user_characters
from feed.helpers.fleet_kills import OUTCOME_LOSS, fleet_kill_report
from srp.models import EveFleetShipReimbursement, ShipReimbursementProgram

from fleets.endpoints.helpers import _fleet_authorized
from fleets.endpoints.schemas import EveFleetSrpLossResponse
from fleets.models import EveFleet

PATH = "/{fleet_id}/my-srp"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetSrpLossResponse], 403: None, 404: None},
    "description": (
        "Ship losses by the caller's characters while in this fleet, on hulls "
        "that have an SRP program. Uncovered hulls and capsules are left out. "
        "filed is true once a reimbursement exists for the killmail."
    ),
}


def _latest_amounts(type_ids: set[int]) -> dict[int, int]:
    amounts: dict[int, int] = {}
    for program in ShipReimbursementProgram.objects.filter(
        eve_type_id__in=type_ids
    ).prefetch_related("amounts"):
        latest = max(
            program.amounts.all(),
            key=lambda row: (row.created_at, row.id),
            default=None,
        )
        if latest and latest.srp_value > 0:
            amounts[program.eve_type_id] = latest.srp_value
    return amounts


def get_fleet_my_srp(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        return 403, None

    character_ids = {c.character_id for c in user_characters(request.user)}
    losses = [
        row
        for row in fleet_kill_report(fleet)["killmails"]
        if row["outcome"] == OUTCOME_LOSS
        and not row["is_capsule"]
        and row["victim_character_id"] in character_ids
        and row["victim_ship_type_id"]
    ]
    if not losses:
        return []

    amounts = _latest_amounts({row["victim_ship_type_id"] for row in losses})
    filed = set(
        EveFleetShipReimbursement.objects.filter(
            killmail_id__in=[row["killmail_id"] for row in losses]
        )
        .exclude(status="withdrawn")
        .values_list("killmail_id", flat=True)
    )
    return [
        EveFleetSrpLossResponse(
            killmail_id=row["killmail_id"],
            killmail_time=row["killmail_time"],
            character_id=row["victim_character_id"],
            character_name=row["victim_character_name"],
            ship_type_id=row["victim_ship_type_id"],
            ship_name=row["victim_ship_name"],
            amount=amounts[row["victim_ship_type_id"]],
            filed=row["killmail_id"] in filed,
        )
        for row in losses
        if row["victim_ship_type_id"] in amounts
    ]

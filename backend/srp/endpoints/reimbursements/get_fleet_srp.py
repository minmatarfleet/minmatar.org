"""GET "" — list SRP requests (filtered by query params, permission-gated)."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from srp.endpoints.reimbursements.helpers import can_update
from srp.endpoints.reimbursements.schemas import EveFleetReimbursementResponse
from srp.models import EveFleetShipReimbursement

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {200: List[EveFleetReimbursementResponse], 403: ErrorResponse},
}


def get_fleet_srp(
    request,
    fleet_id: int | None = None,
    status: str | None = None,
    user_id: int | None = None,
):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }

    reimbursements = EveFleetShipReimbursement.objects.all()
    if status:
        reimbursements = reimbursements.filter(status=status)
    if fleet_id:
        reimbursements = reimbursements.filter(fleet_id=fleet_id)
    if user_id:
        reimbursements = reimbursements.filter(user_id=user_id)

    response = []
    for reimbursement in reimbursements:
        if can_update(request.user, reimbursement):
            response.append(
                {
                    "id": reimbursement.id,
                    "fleet_id": reimbursement.fleet_id,
                    "external_killmail_link": reimbursement.external_killmail_link,
                    "status": reimbursement.status,
                    "character_id": reimbursement.character_id,
                    "character_name": reimbursement.character_name,
                    "primary_character_id": reimbursement.primary_character_id,
                    "primary_character_name": reimbursement.primary_character_name,
                    "ship_type_id": reimbursement.ship_type_id,
                    "ship_name": reimbursement.ship_name,
                    "killmail_id": reimbursement.killmail_id,
                    "amount": reimbursement.amount,
                    "is_corp_ship": reimbursement.is_corp_ship,
                    "corp_id": reimbursement.corp_id,
                    "category": reimbursement.category,
                    "comments": reimbursement.comments,
                    "combat_log_id": (
                        reimbursement.combat_log.id
                        if reimbursement.combat_log
                        else None
                    ),
                }
            )

    return response

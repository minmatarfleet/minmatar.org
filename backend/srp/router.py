from typing import List, Literal

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.models import EveFleet
from srp.helpers import (
    CharacterDoesNotExist,
    PrimaryCharacterDoesNotExist,
    UserCharacterMismatch,
    get_killmail_details,
    get_reimbursement_amount,
    is_valid_for_reimbursement,
    send_decision_notification,
)

from .models import EveFleetShipReimbursement

router = Router(tags=["SRP"])


class CreateEveFleetReimbursementRequest(BaseModel):
    external_killmail_link: str
    fleet_id: int


class UpdateEveFleetReimbursementRequest(BaseModel):
    status: Literal["pending", "approved", "rejected"]


class EveFleetReimbursementResponse(BaseModel):
    id: int
    fleet_id: int
    external_killmail_link: str
    status: str
    character_id: int
    primary_character_id: int
    killmail_id: int
    amount: int


@router.post(
    "",
    auth=AuthBearer(),
    response={200: None, 403: ErrorResponse, 404: ErrorResponse},
    description="Request SRP for a fleet, must be a member of the fleet",
)
def create_fleet_srp(request, payload: CreateEveFleetReimbursementRequest):
    fleet = EveFleet.objects.get(id=payload.fleet_id)
    try:
        details = get_killmail_details(
            payload.external_killmail_link, request.user
        )
    except PrimaryCharacterDoesNotExist:
        return 404, {"detail": "Primary character does not exist"}
    except CharacterDoesNotExist:
        return 404, {"detail": "Character does not exist"}
    except UserCharacterMismatch:
        return 403, {"detail": "Character does not belong to user"}

    valid, reason = is_valid_for_reimbursement(details, fleet)
    if not valid:
        return 403, {"detail": f"Killmail not eligible for SRP, {reason}"}

    reimbursement_amount = get_reimbursement_amount(details.ship)
    if reimbursement_amount == 0:
        return 404, {"detail": "Ship not eligible for SRP"}

    EveFleetShipReimbursement.objects.create(
        fleet=fleet,
        external_killmail_link=payload.external_killmail_link,
        status="pending",
        character_id=details.victim_character.character_id,
        primary_character_id=details.victim_primary_character.character_id,
        killmail_id=details.killmail_id,
        ship_name=details.ship.name,
        amount=reimbursement_amount,
    )


@router.get(
    "",
    auth=AuthBearer(),
    response={200: List[EveFleetReimbursementResponse], 403: ErrorResponse},
)
def get_fleet_srp(request, fleet_id: int = None, status: str = None):
    if not request.user.has_perm("srp.view_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.view_evefleetshipreimbursement"
        }

    reimbursements = EveFleetShipReimbursement.objects.all()
    if fleet_id:
        reimbursements = reimbursements.filter(fleet_id=fleet_id)
    if status:
        reimbursements = reimbursements.filter(status=status)

    response = []
    for reimbursement in reimbursements:
        response.append(
            {
                "id": reimbursement.id,
                "fleet_id": reimbursement.fleet_id,
                "external_killmail_link": reimbursement.external_killmail_link,
                "status": reimbursement.status,
                "character_id": reimbursement.character_id,
                "primary_character_id": reimbursement.primary_character_id,
                "killmail_id": reimbursement.killmail_id,
                "amount": reimbursement.amount,
            }
        )


@router.patch(
    "/{reimbursement_id}",
    auth=AuthBearer(),
    response={200: None, 403: ErrorResponse, 404: ErrorResponse},
    description="Update a SRP request, must have fleets.manage_evefleet permission",
)
def update_fleet_srp(
    request, reimbursement_id: int, payload: UpdateEveFleetReimbursementRequest
):
    if not request.user.has_perm("srp.change_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.change_evefleetshipreimbursement"
        }

    if not EveFleetShipReimbursement.objects.filter(
        id=reimbursement_id
    ).exists():
        return 404, {"detail": "Reimbursement does not exist"}

    reimbursement = EveFleetShipReimbursement.objects.get(id=reimbursement_id)
    reimbursement.status = payload.status
    reimbursement.save()

    send_decision_notification(reimbursement)

    return 200

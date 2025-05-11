from typing import List, Literal, Optional

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
    fleet_id: int = None
    is_corp_ship: bool = False


class UpdateEveFleetReimbursementRequest(BaseModel):
    status: Literal["pending", "approved", "rejected"]


class EveFleetReimbursementResponse(BaseModel):
    """
    Represents a SRP request
    """

    id: int
    fleet_id: Optional[int] = None
    external_killmail_link: str
    status: str
    character_id: int
    character_name: str
    primary_character_id: int
    primary_character_name: str
    ship_type_id: int
    ship_name: str
    killmail_id: int
    amount: int
    is_corp_ship: bool
    corp_id: Optional[int]


class SrpPatchResult(BaseModel):
    database_update_status: str
    evemail_status: str


@router.post(
    "",
    auth=AuthBearer(),
    response={
        200: EveFleetReimbursementResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    description="Request SRP for a fleet, must be a member of the fleet",
)
def create_fleet_srp(request, payload: CreateEveFleetReimbursementRequest):
    if payload.fleet_id:
        fleet = EveFleet.objects.get(id=payload.fleet_id)
    else:
        fleet = None
    try:
        details = get_killmail_details(
            payload.external_killmail_link, request.user
        )
    except PrimaryCharacterDoesNotExist:
        return 404, {"detail": "Primary character does not exist"}
    except CharacterDoesNotExist as e:
        return 404, {"detail": str(e)}
    except UserCharacterMismatch:
        return 403, {"detail": "Character does not belong to user"}
    except Exception:
        return 400, {"detail": "Unexpected error processing killmail"}

    valid, reason = is_valid_for_reimbursement(details, fleet)
    if not valid:
        return 403, {"detail": f"Killmail not eligible for SRP, {reason}"}

    reimbursement_amount = get_reimbursement_amount(details.ship)

    reimbursement = EveFleetShipReimbursement.objects.create(
        fleet=fleet,
        external_killmail_link=payload.external_killmail_link,
        status="pending",
        character_id=details.victim_character.character_id,
        character_name=details.victim_character.character_name,
        primary_character_id=details.victim_primary_character.character_id,
        primary_character_name=details.victim_primary_character.character_name,
        killmail_id=details.killmail_id,
        ship_type_id=details.ship.id,
        ship_name=details.ship.name,
        amount=reimbursement_amount,
        is_corp_ship=payload.is_corp_ship,
        corp_id=(
            details.victim_character.corporation_id
            if details.victim_character
            else None
        ),
    )

    if fleet:
        fleet_id = fleet.id
    else:
        fleet_id = None

    return EveFleetReimbursementResponse(
        id=reimbursement.id,
        fleet_id=fleet_id,
        external_killmail_link=payload.external_killmail_link,
        status="pending",
        character_id=details.victim_character.character_id,
        character_name=details.victim_character.character_name,
        primary_character_id=details.victim_primary_character.character_id,
        primary_character_name=details.victim_primary_character.character_name,
        ship_type_id=details.ship.id,
        ship_name=details.ship.name,
        killmail_id=details.killmail_id,
        amount=reimbursement_amount,
        is_corp_ship=reimbursement.is_corp_ship,
        corp_id=(
            details.victim_character.corporation_id
            if details.victim_character
            else None
        ),
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
                "character_name": reimbursement.character_name,
                "primary_character_id": reimbursement.primary_character_id,
                "primary_character_name": reimbursement.primary_character_name,
                "ship_type_id": reimbursement.ship_type_id,
                "ship_name": reimbursement.ship_name,
                "killmail_id": reimbursement.killmail_id,
                "amount": reimbursement.amount,
                "is_corp_ship": reimbursement.is_corp_ship,
                "corp_id": reimbursement.corp_id,
            }
        )

    return response


@router.patch(
    "/{reimbursement_id}",
    auth=AuthBearer(),
    response={200: SrpPatchResult, 403: ErrorResponse, 404: ErrorResponse},
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

    try:
        send_decision_notification(reimbursement)
        mail_result = "Success"
    except Exception as err:
        mail_result = f"Error sending mail: {err}"

    return 200, SrpPatchResult(
        database_update_status="Success",
        evemail_status=mail_result,
    )

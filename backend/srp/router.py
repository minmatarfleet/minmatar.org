import logging

from typing import List, Literal, Optional
from enum import Enum

from django.contrib.auth.models import User
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse, create_error_id
from authentication import AuthBearer
from fleets.models import EveFleet
from srp.helpers import (
    CharacterDoesNotExist,
    PrimaryCharacterDoesNotExist,
    UserCharacterMismatch,
    InvalidKillmailLink,
    get_killmail_details,
    get_reimbursement_amount,
    is_valid_for_reimbursement,
    send_decision_notification,
)

from .models import EveFleetShipReimbursement

router = Router(tags=["SRP"])

logger = logging.getLogger(__name__)


class SrpCategory(str, Enum):
    LOGISTICS = "logistics"
    SUPPORT = "support"
    DPS = "dps"
    CAPITAL = "capital"


class CreateEveFleetReimbursementRequest(BaseModel):
    external_killmail_link: str
    fleet_id: int = None
    is_corp_ship: bool = False
    category: Optional[SrpCategory] = None
    comments: Optional[str] = None


class UpdateEveFleetReimbursementRequest(BaseModel):
    status: Literal["pending", "approved", "rejected", "withdrawn"]


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
    corp_id: Optional[int] = None
    category: Optional[SrpCategory] = None
    comments: Optional[str] = None


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
    logger.info(
        "Creating SRP request for %s, %s",
        request.user.username,
        payload.external_killmail_link,
    )

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
    except InvalidKillmailLink:
        return 400, ErrorResponse.log(
            "Killmail link not valid",
            f"Bad killmail link: '{payload.external_killmail_link}'",
        )
    except Exception as e:
        return 400, ErrorResponse.log(
            "Unexpected error processing killmail",
            f"Error parsing killmail: user={request.user} killmail={payload.external_killmail_link} error={e}",
        )

    if duplicate_kill(details):
        return 400, {"detail": "SRP already exists for this killmail"}

    valid, reason = is_valid_for_reimbursement(details, fleet)
    if not valid:
        return 403, {"detail": f"Killmail not eligible for SRP, {reason}"}

    reimbursement_amount = get_reimbursement_amount(details.ship)

    reimbursement = EveFleetShipReimbursement.objects.create(
        fleet=fleet,
        user=request.user,
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
        category=payload.category if payload.category else None,
        comments=payload.comments,
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
        category=reimbursement.category,
        comments=reimbursement.comments,
    )


def duplicate_kill(details) -> bool:
    return (
        EveFleetShipReimbursement.objects.filter(
            killmail_id=details.killmail_id
        )
        .exclude(status="rejected")
        .exclude(status="withdrawn")
        .exists()
    )


@router.get(
    "",
    auth=AuthBearer(),
    response={200: List[EveFleetReimbursementResponse], 403: ErrorResponse},
)
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
                }
            )

    return response


def can_update(user: User, reimbursement: EveFleetShipReimbursement) -> bool:
    if reimbursement.user == user:
        return True
    if user.has_perm("srp.change_evefleetshipreimbursement"):
        return True
    return False


@router.patch(
    "/{reimbursement_id}",
    auth=AuthBearer(),
    response={200: SrpPatchResult, 403: ErrorResponse, 404: ErrorResponse},
    description="Update a SRP request, must have fleets.manage_evefleet permission",
)
def update_fleet_srp(
    request, reimbursement_id: int, payload: UpdateEveFleetReimbursementRequest
):
    reimbursement = EveFleetShipReimbursement.objects.filter(
        id=reimbursement_id
    ).first()

    if not reimbursement:
        return 404, {"detail": "Reimbursement does not exist"}

    if not can_update(request.user, reimbursement):
        return 403, {
            "detail": "User missing permission srp.change_evefleetshipreimbursement"
        }

    if not request.user.has_perm("srp.change_evefleetshipreimbursement"):
        if payload.status != "withdrawn":
            return 403, {"detail": "Permission denied"}

    reimbursement.status = payload.status
    reimbursement.save()

    if reimbursement.status in ["approved", "rejected"]:
        try:
            send_decision_notification(reimbursement)
            mail_result = "Success"
        except Exception as err:
            mail_result = f"Error sending mail: {err}"
    else:
        mail_result = "N/A"

    return 200, SrpPatchResult(
        database_update_status="Success",
        evemail_status=mail_result,
    )

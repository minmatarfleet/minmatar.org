"""POST \"\" — create an SRP request for a killmail."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from fleets.models import EveFleet
from srp.endpoints.requests.helpers import duplicate_kill
from srp.endpoints.requests.schemas import CreateSrpRequest, SrpRequestResponse
from srp.helpers import (
    CharacterDoesNotExist,
    InvalidKillmailLink,
    PrimaryCharacterDoesNotExist,
    UserCharacterMismatch,
    get_killmail_details,
    get_latest_program_amount,
    is_valid_for_reimbursement,
)
from srp.models import EveFleetShipReimbursement

PATH = ""
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: SrpRequestResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "description": "Create an SRP request (fleet or non-fleet killmail).",
}

logger = logging.getLogger(__name__)


def create_srp_request(request, payload: CreateSrpRequest):
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

    reimbursement_program_amount = get_latest_program_amount(details.ship)
    if not reimbursement_program_amount:
        return 403, {
            "detail": "Ship type is not covered by the reimbursement program"
        }
    reimbursement_amount = reimbursement_program_amount.srp_value

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
        reimbursement_program_amount=reimbursement_program_amount,
        is_corp_ship=payload.is_corp_ship,
        corp_id=(
            details.victim_character.corporation_id
            if details.victim_character
            else None
        ),
        category=payload.category if payload.category else None,
        comments=payload.comments,
        combat_log_id=payload.combat_log_id if payload.combat_log_id else None,
    )

    if fleet:
        fleet_id = fleet.id
    else:
        fleet_id = None

    return SrpRequestResponse(
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

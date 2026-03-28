"""POST resolve-killmail — preview killmail and candidate fleets for SRP."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from srp.endpoints.resolve.schemas import (
    CandidateFleetResponse,
    ResolveKillmailRequest,
    ResolveKillmailResponse,
)
from srp.fleet_candidates import (
    get_candidate_fleets_queryset,
    serialize_candidate_fleets,
)
from srp.helpers import (
    CharacterDoesNotExist,
    InvalidKillmailLink,
    PrimaryCharacterDoesNotExist,
    UserCharacterMismatch,
    get_killmail_details,
)

PATH = "resolve-killmail"
METHOD = "post"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: ResolveKillmailResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def resolve_killmail_for_srp(request, payload: ResolveKillmailRequest):
    if not request.user.has_perm("srp.add_evefleetshipreimbursement"):
        return 403, {
            "detail": "User missing permission srp.add_evefleetshipreimbursement"
        }
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

    fleets_qs = get_candidate_fleets_queryset(details.timestamp)
    candidate_fleets = [
        CandidateFleetResponse.model_validate(d)
        for d in serialize_candidate_fleets(fleets_qs)
    ]
    return ResolveKillmailResponse(
        killmail_time=details.timestamp,
        killmail_id=details.killmail_id,
        victim_character_id=details.victim_character.character_id,
        victim_character_name=details.victim_character.character_name,
        ship_type_id=details.ship.id,
        ship_name=details.ship.name,
        candidate_fleets=candidate_fleets,
    )

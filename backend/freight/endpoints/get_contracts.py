"""GET /contracts – outstanding and in-progress freight contracts."""

from typing import List

from ninja import Router

from eveonline.helpers.characters import character_primary
from freight.models import EveFreightContract
from freight.endpoints.schemas import FreightContractResponse

router = Router(tags=["Freight"])

ACTIVE_STATUSES = ["outstanding", "in_progress"]


def _completed_by_character(contract):
    """Resolve completed_by User to a character (primary preferred, else first)."""
    if not contract.completed_by_id:
        return None
    user = contract.completed_by
    try:
        primary = user.eveplayer.primary_character
        if primary:
            return primary
    except Exception:
        pass
    chars = list(user.evecharacter_set.all())
    return min(chars, key=lambda c: (c.character_name or ""), default=None)


def _issuer_display_character(contract):
    """Resolve issuer to primary character for display (prefer primary over alt)."""
    if not contract.issuer_id:
        return None
    try:
        primary = character_primary(contract.issuer)
        return primary if primary else contract.issuer
    except Exception:
        return contract.issuer


def _build_contract_response(c):
    completed_by_char = _completed_by_character(c)
    issuer_char = _issuer_display_character(c)
    return FreightContractResponse(
        contract_id=c.contract_id,
        status=c.status,
        start_location_name=c.start_location_name,
        end_location_name=c.end_location_name,
        volume=c.volume,
        collateral=c.collateral,
        reward=c.reward,
        date_issued=c.date_issued.isoformat() if c.date_issued else "",
        date_completed=(
            c.date_completed.isoformat() if c.date_completed else None
        ),
        issuer_id=issuer_char.character_id if issuer_char else None,
        issuer_character_name=(
            issuer_char.character_name if issuer_char else None
        ),
        completed_by_id=(
            completed_by_char.character_id if completed_by_char else None
        ),
        completed_by_character_name=(
            completed_by_char.character_name if completed_by_char else None
        ),
    )


@router.get(
    "/contracts",
    description="Fetch outstanding and in-progress freight contracts.",
    response=List[FreightContractResponse],
)
def get_contracts(request):
    qs = (
        EveFreightContract.objects.filter(status__in=ACTIVE_STATUSES)
        .select_related(
            "issuer",
            "issuer__user",
            "issuer__user__eveplayer",
            "issuer__user__eveplayer__primary_character",
            "completed_by",
            "completed_by__eveplayer",
            "completed_by__eveplayer__primary_character",
        )
        .prefetch_related("completed_by__evecharacter_set")
        .order_by("-date_issued")
    )
    return [_build_contract_response(c) for c in qs]

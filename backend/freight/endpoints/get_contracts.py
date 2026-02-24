"""GET /contracts – outstanding and in-progress freight contracts."""

from typing import List

from ninja import Router

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


def _build_contract_response(c):
    completed_by_char = _completed_by_character(c)
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
        issuer_id=c.issuer.character_id if c.issuer_id else None,
        issuer_character_name=(
            c.issuer.character_name if c.issuer_id else None
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
            "completed_by",
            "completed_by__eveplayer",
            "completed_by__eveplayer__primary_character",
        )
        .prefetch_related("completed_by__evecharacter_set")
        .order_by("-date_issued")
    )
    return [_build_contract_response(c) for c in qs]

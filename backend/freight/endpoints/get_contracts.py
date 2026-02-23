"""GET /contracts – outstanding and in-progress freight contracts."""

from typing import List

from ninja import Router

from freight.models import EveFreightContract
from freight.endpoints.schemas import FreightContractResponse

router = Router(tags=["Freight"])

ACTIVE_STATUSES = ["outstanding", "in_progress"]


def _completed_by_display_name(contract):
    """Resolve completed_by User to a character name (primary preferred)."""
    if not contract.completed_by_id:
        return None
    user = contract.completed_by
    try:
        primary = user.eveplayer.primary_character
        if primary:
            return primary.character_name
    except Exception:
        pass
    chars = list(user.evecharacter_set.all())
    first = min(chars, key=lambda c: (c.character_name or ""), default=None)
    return first.character_name if first else None


def _build_contract_response(c):
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
        completed_by_character_name=_completed_by_display_name(c),
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
            "completed_by",
            "completed_by__eveplayer",
            "completed_by__eveplayer__primary_character",
        )
        .prefetch_related("completed_by__evecharacter_set")
        .order_by("-date_issued")
    )
    return [_build_contract_response(c) for c in qs]

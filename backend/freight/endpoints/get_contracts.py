"""GET /contracts – outstanding and in-progress freight contracts."""

from typing import List

from ninja import Router

from freight.endpoints.schemas import FreightContractResponse
from freight.helpers.contract_display import (
    FREIGHT_CORP_FALLBACK_NAME,
    completed_by_display,
    display_character,
    freight_corp_display_name,
    resolve_characters,
    resolve_location_names,
)
from freight.models import FREIGHT_CORPORATION_ID, FreightContract

router = Router(tags=["Freight"])

# Re-export for any callers that still import these from get_contracts.
_resolve_location_names = resolve_location_names
_resolve_characters = resolve_characters
_display_character = display_character
_completed_by_display = completed_by_display
_freight_corp_display_name = freight_corp_display_name


def _build_contract_response(
    c, location_names, char_lookup, freight_corp_name=None
):
    start_name = (
        location_names.get(int(c.start_location_id), "Unknown")
        if c.start_location_id
        else "Unknown"
    )
    end_name = (
        location_names.get(int(c.end_location_id), "Unknown")
        if c.end_location_id
        else "Unknown"
    )

    issuer_display = display_character(char_lookup.get(c.issuer_id))

    completed_by_id = None
    completed_by_character_name = None
    if c.acceptor_id == FREIGHT_CORPORATION_ID:
        # Corp-accepted: no character portrait; name only for servicing column.
        completed_by_character_name = (
            freight_corp_name or FREIGHT_CORP_FALLBACK_NAME
        )
    elif c.acceptor_id:
        acceptor_char = char_lookup.get(c.acceptor_id)
        completed_by = completed_by_display(acceptor_char)
        if completed_by:
            completed_by_id = completed_by.character_id
            completed_by_character_name = completed_by.character_name
        else:
            # Acceptor known from ESI but not in EveCharacter yet.
            completed_by_id = c.acceptor_id

    return FreightContractResponse(
        contract_id=c.contract_id,
        status=c.status,
        start_location_name=start_name,
        end_location_name=end_name,
        volume=int(c.volume or 0),
        collateral=int(c.collateral or 0),
        reward=int(c.reward or 0),
        date_issued=c.date_issued.isoformat() if c.date_issued else "",
        date_completed=(
            c.date_completed.isoformat() if c.date_completed else None
        ),
        issuer_id=issuer_display.character_id if issuer_display else None,
        issuer_character_name=(
            issuer_display.character_name if issuer_display else None
        ),
        completed_by_id=completed_by_id,
        completed_by_character_name=completed_by_character_name,
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


def prepare_contract_responses(contracts):
    """Bulk-resolve related data and build FreightContractResponse list."""
    location_ids = set()
    character_ids = set()
    has_freight_corp_acceptor = False
    for c in contracts:
        if c.start_location_id:
            location_ids.add(int(c.start_location_id))
        if c.end_location_id:
            location_ids.add(int(c.end_location_id))
        if c.issuer_id:
            character_ids.add(c.issuer_id)
        if c.acceptor_id == FREIGHT_CORPORATION_ID:
            has_freight_corp_acceptor = True
        elif c.acceptor_id:
            character_ids.add(c.acceptor_id)

    location_names = resolve_location_names(location_ids)
    char_lookup = resolve_characters(character_ids)
    freight_corp_name = (
        freight_corp_display_name() if has_freight_corp_acceptor else None
    )

    return [
        _build_contract_response(
            c, location_names, char_lookup, freight_corp_name
        )
        for c in contracts
    ]


@router.get(
    "/contracts",
    description="Fetch outstanding and in-progress freight contracts.",
    response=List[FreightContractResponse],
)
def get_contracts(request):
    contracts = list(FreightContract.objects.active().order_by("-date_issued"))
    return prepare_contract_responses(contracts)

"""GET /contracts – outstanding and in-progress buyback contracts."""

from typing import List

from ninja import Router

from buyback.endpoints.schemas import BuybackContractResponse
from buyback.models import (
    BUYBACK_CORP_FALLBACK_NAME,
    BUYBACK_CORPORATION_ID,
    BuybackContract,
)
from eveonline.helpers.corporation_contract_display import (
    acceptor_display,
    corp_display_name,
    display_character,
    resolve_characters,
    resolve_location_names,
)

router = Router(tags=["Buyback"])


def _build_contract_response(c, location_names, char_lookup, corp_name=None):
    location_id = c.start_location_id or c.end_location_id
    location_name = (
        location_names.get(int(location_id), "Unknown")
        if location_id
        else "Unknown"
    )

    issuer_display = display_character(char_lookup.get(c.issuer_id))
    # External buyback issuers are often absent from EveCharacter.
    if issuer_display:
        issuer_id = issuer_display.character_id
        issuer_character_name = issuer_display.character_name
    elif c.issuer_id:
        issuer_id = c.issuer_id
        issuer_character_name = "Unknown"
    else:
        issuer_id = None
        issuer_character_name = None

    acceptor_id = None
    acceptor_character_name = None
    if c.acceptor_id == BUYBACK_CORPORATION_ID:
        acceptor_character_name = corp_name or BUYBACK_CORP_FALLBACK_NAME
    elif c.acceptor_id:
        acceptor_char = char_lookup.get(c.acceptor_id)
        acceptor = acceptor_display(acceptor_char)
        if acceptor:
            acceptor_id = acceptor.character_id
            acceptor_character_name = acceptor.character_name
        else:
            acceptor_id = c.acceptor_id

    return BuybackContractResponse(
        contract_id=c.contract_id,
        status=c.status,
        location_name=location_name,
        volume=int(c.volume or 0),
        price=int(c.price or 0),
        title=c.title or "",
        date_issued=c.date_issued.isoformat() if c.date_issued else "",
        date_completed=(
            c.date_completed.isoformat() if c.date_completed else None
        ),
        issuer_id=issuer_id,
        issuer_character_name=issuer_character_name,
        acceptor_id=acceptor_id,
        acceptor_character_name=acceptor_character_name,
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


def prepare_contract_responses(contracts):
    location_ids = set()
    character_ids = set()
    has_corp_acceptor = False
    for c in contracts:
        if c.start_location_id:
            location_ids.add(int(c.start_location_id))
        if c.end_location_id:
            location_ids.add(int(c.end_location_id))
        if c.issuer_id:
            character_ids.add(c.issuer_id)
        if c.acceptor_id == BUYBACK_CORPORATION_ID:
            has_corp_acceptor = True
        elif c.acceptor_id:
            character_ids.add(c.acceptor_id)

    location_names = resolve_location_names(location_ids)
    char_lookup = resolve_characters(character_ids)
    corp_name = (
        corp_display_name(BUYBACK_CORPORATION_ID, BUYBACK_CORP_FALLBACK_NAME)
        if has_corp_acceptor
        else None
    )

    return [
        _build_contract_response(c, location_names, char_lookup, corp_name)
        for c in contracts
    ]


@router.get(
    "/contracts",
    description="Fetch outstanding and in-progress buyback contracts.",
    response=List[BuybackContractResponse],
)
def get_contracts(request):
    contracts = list(BuybackContract.objects.active().order_by("-date_issued"))
    return prepare_contract_responses(contracts)

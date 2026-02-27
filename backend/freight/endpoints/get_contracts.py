"""GET /contracts – outstanding and in-progress freight contracts."""

from typing import List

from ninja import Router

from eveonline.helpers.characters import character_primary
from eveonline.models import EveCharacter
from eveuniverse.models import EveStation
from freight.models import FreightContract, FREIGHT_CORPORATION_ID
from freight.endpoints.schemas import FreightContractResponse
from structures.models import EveStructure

router = Router(tags=["Freight"])


def _resolve_location_names(location_ids):
    """Bulk-resolve location IDs to display names."""
    if not location_ids:
        return {}
    names = {}
    station_ids = {
        lid for lid in location_ids if 60_000_000 < lid < 61_000_000
    }
    structure_ids = location_ids - station_ids

    if station_ids:
        for station in EveStation.objects.filter(
            id__in=station_ids
        ).select_related("eve_solar_system"):
            if station.eve_solar_system:
                names[station.id] = station.eve_solar_system.name
            else:
                names[station.id] = station.name

    if structure_ids:
        for structure in EveStructure.objects.filter(id__in=structure_ids):
            names[structure.id] = structure.name

    for lid in location_ids:
        if lid not in names:
            names[lid] = "Unknown" if lid in station_ids else "Structure"

    return names


def _resolve_characters(character_ids):
    """Bulk-fetch EveCharacters, pre-loading the user → primary-character chain."""
    if not character_ids:
        return {}
    chars = EveCharacter.objects.filter(
        character_id__in=character_ids
    ).select_related(
        "user__eveplayer__primary_character",
        "token__user__eveplayer__primary_character",
    )
    return {c.character_id: c for c in chars}


def _display_character(char):
    """Resolve an EveCharacter to its User's primary character, falling back to itself."""
    if not char:
        return None
    try:
        primary = character_primary(char)
        return primary if primary else char
    except Exception:
        return char


def _completed_by_display(char):
    """Resolve acceptor EveCharacter → User → primary character for display."""
    if not char:
        return None
    user = char.user or (
        char.token.user if getattr(char, "token", None) else None
    )
    if not user:
        return None
    try:
        primary = user.eveplayer.primary_character
        if primary:
            return primary
    except Exception:
        pass
    chars = list(user.evecharacter_set.all())
    return min(chars, key=lambda c: (c.character_name or ""), default=None)


def _build_contract_response(c, location_names, char_lookup):
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

    issuer_display = _display_character(char_lookup.get(c.issuer_id))

    acceptor_char = None
    if c.acceptor_id and c.acceptor_id != FREIGHT_CORPORATION_ID:
        acceptor_char = char_lookup.get(c.acceptor_id)
    completed_by = _completed_by_display(acceptor_char)

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
        completed_by_id=(completed_by.character_id if completed_by else None),
        completed_by_character_name=(
            completed_by.character_name if completed_by else None
        ),
    )


def prepare_contract_responses(contracts):
    """Bulk-resolve related data and build FreightContractResponse list."""
    location_ids = set()
    character_ids = set()
    for c in contracts:
        if c.start_location_id:
            location_ids.add(int(c.start_location_id))
        if c.end_location_id:
            location_ids.add(int(c.end_location_id))
        if c.issuer_id:
            character_ids.add(c.issuer_id)
        if c.acceptor_id and c.acceptor_id != FREIGHT_CORPORATION_ID:
            character_ids.add(c.acceptor_id)

    location_names = _resolve_location_names(location_ids)
    char_lookup = _resolve_characters(character_ids)

    return [
        _build_contract_response(c, location_names, char_lookup)
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

"""Helpers for deciding which characters/corporations to fetch contracts for."""

from esi.models import Token

from eveonline.models import EveAlliance, EveCharacter, EveCorporation

CORPORATION_CONTRACT_SCOPES = ["esi-contracts.read_corporation_contracts.v1"]
CHARACTER_CONTRACT_SCOPES = ["esi-contracts.read_character_contracts.v1"]
STRUCTURE_MARKET_SCOPES = ["esi-markets.structure_markets.v1"]
CONTRACT_FETCH_SPREAD_SECONDS = 4 * 3600  # 4 hours
MARKET_ITEM_HISTORY_SPREAD_SECONDS = 4 * 3600  # 4 hours


def alliance_corporation_ids():
    """Corporation IDs for all corporations in tracked alliances."""
    return set(
        EveCorporation.objects.filter(
            alliance__in=EveAlliance.objects.all()
        ).values_list("corporation_id", flat=True)
    )


def get_character_with_contract_scope_for_corporation(
    corporation_id: int,
) -> int | None:
    """
    Return a character_id in this corporation with a valid token that has
    corporation contract scope, or None if none found.
    """
    for character in (
        EveCharacter.objects.filter(corporation_id=corporation_id)
        .exclude(token__isnull=True)
        .exclude(esi_suspended=True)
    ):
        if Token.get_token(
            character.character_id, CORPORATION_CONTRACT_SCOPES
        ):
            return character.character_id
    return None


def get_character_with_structure_markets_scope() -> int | None:
    """
    Return a character_id with a valid token that has structure market scope
    (for fetching sell orders in structures). Prefer alliance characters.
    """
    alliance_ids = set(
        EveAlliance.objects.values_list("alliance_id", flat=True)
    )
    for character in (
        EveCharacter.objects.filter(alliance_id__in=alliance_ids)
        .exclude(token__isnull=True)
        .exclude(esi_suspended=True)
    ):
        if Token.get_token(character.character_id, STRUCTURE_MARKET_SCOPES):
            return character.character_id
    return None


def known_contract_issuer_ids():
    """Set of issuer IDs we consider 'known' (alliance characters + alliance corps)."""
    alliance_ids = set(
        EveAlliance.objects.values_list("alliance_id", flat=True)
    )
    character_ids = set(
        EveCharacter.objects.filter(alliance_id__in=alliance_ids).values_list(
            "character_id", flat=True
        )
    )
    corp_ids = alliance_corporation_ids()
    return character_ids | corp_ids

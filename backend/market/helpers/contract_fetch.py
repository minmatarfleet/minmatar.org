"""Helpers for structure markets and market contract issuer checks."""

from esi.models import Token

from eveonline.models import EveAlliance, EveCharacter, EveCorporation

STRUCTURE_MARKET_SCOPES = ["esi-markets.structure_markets.v1"]


def _alliance_corporation_ids():
    """Corporation IDs for all corporations in tracked alliances."""
    return set(
        EveCorporation.objects.filter(
            alliance__in=EveAlliance.objects.all()
        ).values_list("corporation_id", flat=True)
    )


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
    corp_ids = _alliance_corporation_ids()
    return character_ids | corp_ids

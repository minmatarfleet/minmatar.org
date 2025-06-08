from eveonline.client import EsiClient
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveFaction,
)


def create_or_update_affiliation_entities(
    corporation_id: int,
    alliance_id: int | None = None,
    faction_id: int | None = None,
):
    corporation, _ = EveCorporation.objects.get_or_create(
        corporation_id=corporation_id
    )
    if alliance_id:
        alliance, _ = EveAlliance.objects.get_or_create(
            alliance_id=alliance_id
        )
        if not corporation.alliance or corporation.alliance != alliance:
            corporation.alliance = alliance
            corporation.save()

    if faction_id:
        faction = EsiClient(None).get_faction(faction_id)
        if not corporation.faction or corporation.faction != faction:
            corporation.faction = faction
            corporation.save()


def update_character_with_affiliations(
    character_id: int,
    corporation_id: int,
    alliance_id: int | None = None,
    faction_id: int | None = None,
) -> bool:
    character = EveCharacter.objects.get(character_id=character_id)
    updated = False
    if (corporation_id and not character.corporation) or (
        corporation_id
        and corporation_id != character.corporation.corporation_id
    ):
        character.corporation = EveCorporation.objects.get(
            corporation_id=corporation_id
        )
        updated = True

    if (alliance_id and not character.alliance) or (
        alliance_id and alliance_id != character.alliance.alliance_id
    ):
        character.alliance = EveAlliance.objects.get(alliance_id=alliance_id)
        updated = True

    if not alliance_id and character.alliance:
        character.alliance = None
        updated = True

    if (
        (faction_id and not character.faction)
        or faction_id
        and (faction_id != character.faction.id)
    ):
        character.faction = EveFaction.objects.get(id=faction_id)
        updated = True

    if not faction_id and character.faction:
        character.faction = None
        updated = True

    if updated:
        character.save()
    return updated

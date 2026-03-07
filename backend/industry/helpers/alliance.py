"""Alliance-scoping helper for industry planetary and other alliance-wide views."""

from eveonline.models import EveAlliance, EveCharacter


def get_alliance_character_ids():
    """
    Return the set of EVE character IDs for characters in tracked alliances.
    Use for filtering planetary output, planets, etc. to "our alliance".
    """
    alliance_ids = set(
        EveAlliance.objects.values_list("alliance_id", flat=True)
    )
    return set(
        EveCharacter.objects.filter(alliance_id__in=alliance_ids).values_list(
            "character_id", flat=True
        )
    )

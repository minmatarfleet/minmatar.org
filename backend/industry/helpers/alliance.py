"""Alliance-scoping helper for industry planetary and other alliance-wide views."""

from eveonline.helpers.alliances import tracked_alliance_ids
from eveonline.models import EveCharacter


def get_alliance_character_ids():
    """
    Return the set of EVE character IDs for characters in scope.

    Any character whose alliance_id appears in any EveAlliance row is in scope.
    Use for filtering planetary output, planets, etc. to "our" alliances.
    """
    return set(
        EveCharacter.objects.filter(
            alliance_id__in=tracked_alliance_ids()
        ).values_list("character_id", flat=True)
    )

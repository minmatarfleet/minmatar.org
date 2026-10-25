"""Which of the FC's characters runs the fleet in game.

An FC usually forms the fleet on their main. When they form it on another
of their characters, starting the fleet finds that character (main first),
and the site shows the FC as their main, "in game as" the other character.
Public pages show only the in-game character (docs/fleets/fleet-on-alt.md).
"""

import logging

from django.contrib.auth.models import User

from eveonline.client import EsiClient
from eveonline.helpers.characters import (
    user_characters,
    user_primary_character,
)
from eveonline.models import EveCharacter

logger = logging.getLogger(__name__)

NOT_IN_FLEET = "not in a fleet"
NOT_BOSS = "not the fleet commander"
NO_BOSS = "None of your characters is the fleet boss"


def active_fleet_as_boss(character: EveCharacter, fleet_id: int) -> dict:
    """ESI's active fleet for ``character``, who must be its boss.

    Raises RuntimeError naming why not (NOT_IN_FLEET, NOT_BOSS, an ESI error).
    """
    esi_response = EsiClient(character).get_active_fleet()
    if not esi_response.success():
        if not esi_response.data:
            msg = f"ESI error {esi_response.response_code} starting fleet {fleet_id}"
        elif "Character is not in a fleet" in esi_response.data["error"]:
            msg = f"Character {character.character_name} {NOT_IN_FLEET} (starting fleet {fleet_id})"
        else:
            msg = f"ESI error {esi_response.response_code} starting fleet {fleet_id}, {esi_response.data}"
        raise RuntimeError(msg)

    response = esi_response.data
    # Only the in-game fleet boss may link/start tracking.
    # Otherwise a member can "steal" an existing EveFleetInstance.
    if response.get("fleet_boss_id") != character.character_id:
        raise RuntimeError(
            f"Character {character.character_name} is {NOT_BOSS} "
            f"(starting fleet {fleet_id})"
        )
    return response


def find_fleet_boss(user: User, fleet_id: int) -> tuple[EveCharacter, dict]:
    """The user's character that is fleet boss in game, and its ESI fleet.

    Tries the main first, then the user's other characters by name. With
    only a main, its own error is raised; otherwise NO_BOSS, naming the
    characters checked.
    """
    primary = user_primary_character(user)
    checked = []
    first_error = None
    if primary:
        try:
            return primary, active_fleet_as_boss(primary, fleet_id)
        except RuntimeError as error:
            first_error = error
            checked.append(primary.character_name)

    others = [
        character
        for character in user_characters(user).order_by("character_name")
        if not primary or character.character_id != primary.character_id
    ]
    for character in others:
        try:
            return character, active_fleet_as_boss(character, fleet_id)
        except RuntimeError:
            checked.append(character.character_name)

    if first_error and len(checked) == 1:
        raise first_error
    raise RuntimeError(f"{NO_BOSS} (checked {', '.join(checked)})")


def fleet_boss_alt(fleet) -> EveCharacter | None:
    """The FC's other character that is boss in game, or None.

    None when the fleet isn't tracked, the boss is the FC's main, or the
    boss isn't one of the FC's characters (boss passed to someone else).
    """
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstance

    boss_id = (
        EveFleetInstance.objects.filter(eve_fleet=fleet)
        .order_by("-start_time")
        .values_list("boss_id", flat=True)
        .first()
    )
    return alt_for_boss(fleet, boss_id, fleet.fleet_commander)


def alt_for_boss(
    fleet, boss_id: int | None, primary: EveCharacter | None
) -> EveCharacter | None:
    """``boss_id`` as one of the FC's other characters, or None.

    For callers that already hold the boss id and the FC's main: no query
    when the boss is the main.
    """
    if not boss_id or not fleet.created_by_id:
        return None
    if primary and primary.character_id == boss_id:
        return None
    return EveCharacter.objects.filter(
        character_id=boss_id, user_id=fleet.created_by_id
    ).first()


def in_game_fleet_commander(fleet) -> EveCharacter | None:
    """The character pilots see running the fleet: the alt, else the main."""
    return fleet_boss_alt(fleet) or fleet.fleet_commander

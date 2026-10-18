"""Who may see a fleet's fights, and the response the API sends."""

from __future__ import annotations

from django.utils import timezone

from eveonline.helpers.characters import user_characters
from fleets.helpers.fights import timeline as fights


def flew_in(user, fleet) -> bool:
    """True when any of the user's characters was in the fleet."""
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstanceMember

    ids = [character.character_id for character in user_characters(user)]
    return EveFleetInstanceMember.objects.filter(
        eve_fleet_instance__eve_fleet=fleet, character_id__in=ids
    ).exists()


def may_view(user, fleet, *, manager: bool, live: bool) -> bool:
    """While the fleet is out, only its managers and its pilots see fights.

    Afterwards anyone who can see the fleet can.
    """
    if not live or manager:
        return True
    return flew_in(user, fleet)


def fights_response(fleet, *, can_edit: bool, live: bool) -> dict:
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetFightTimeline
    from fleets.tasks import rebuild_fight_timeline

    timeline = EveFleetFightTimeline.objects.filter(eve_fleet=fleet).first()
    if timeline is None or not timeline.payload:
        # Fleets from before the timeline existed, or one that just started.
        rebuild_fight_timeline.delay(fleet.id)
        return {"fleet_id": fleet.id, "status": "building", "live": live}
    if live:
        status = "live"
    elif timeline.settled_at:
        status = "settled"
    else:
        status = "settling"
    return {
        **timeline.payload,
        "fleet_id": fleet.id,
        "status": status,
        "live": live,
        "can_edit": can_edit,
        "computed_at": timeline.computed_at,
        "settled_at": timeline.settled_at,
        "feed_behind_since": (
            fights.feed_behind_since(timezone.now()) if live else None
        ),
    }


def editable_fleet(request, fleet_id: int):
    """``(fleet, None)`` when the user may edit its rounds, else
    ``(None, (status, body))`` for the endpoint to return."""
    # pylint: disable=import-outside-toplevel
    from fleets.endpoints.helpers import _fleet_manager
    from fleets.models import EveFleet, EveFleetFightTimeline

    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return None, (404, None)
    if not _fleet_manager(request, fleet):
        return None, (403, None)
    if not EveFleetFightTimeline.objects.filter(eve_fleet=fleet).exists():
        return None, (404, None)
    return fleet, None


def recut_response(fleet) -> dict:
    """Re-cut after an edit and send the result back."""
    fights.recut_fleet(fleet)
    return fights_response(fleet, can_edit=True, live=fights.is_live(fleet))

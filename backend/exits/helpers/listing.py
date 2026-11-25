"""Rows for the CEO's Departures tab: one per person, alts folded in."""

from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCorporation,
)
from exits.helpers.grouping import group
from exits.models import STATUS_CONFIRMED, Departure

STATE_OPEN = "open"
STATE_ANSWERED = "answered"
STATE_ALL = "all"
STATES = (STATE_OPEN, STATE_ANSWERED, STATE_ALL)


def _joined_dates(character_ids, corporation_id) -> dict[int, list]:
    """Each character's start dates in this corporation, newest first, in one query."""
    joined: dict[int, list] = {}
    for character_id, start in (
        EveCharacterCorporationHistory.objects.filter(
            character__character_id__in=character_ids,
            corporation_id=corporation_id,
        )
        .order_by("-start_date")
        .values_list("character__character_id", "start_date")
    ):
        joined.setdefault(character_id, []).append(start)
    return joined


def _months_in_corporation(starts, left_at):
    """Months since the last time they joined before leaving."""
    joined = next((start for start in starts if start <= left_at), None)
    if joined is None:
        return None
    return max(0, (left_at - joined).days // 30)


def survey_sent_at(departure_ids) -> dict[int, object]:
    """When each departure's survey went out."""
    # Imported here: surveys depends on exits, not the other way round.
    from surveys.models import (  # pylint: disable=import-outside-toplevel
        ExitSurveyInvite,
    )

    return dict(
        ExitSurveyInvite.objects.filter(
            departure_id__in=departure_ids
        ).values_list("departure_id", "sent_at")
    )


def departure_groups(corporation: EveCorporation, state: str = STATE_OPEN):
    departures = Departure.objects.filter(
        corporation=corporation, status=STATUS_CONFIRMED
    ).prefetch_related("flags")
    if state == STATE_OPEN:
        departures = departures.filter(reason="")
    elif state == STATE_ANSWERED:
        departures = departures.exclude(reason="")
    departures = list(departures)

    character_ids = {d.character_id for d in departures}
    names = dict(
        EveCharacter.objects.filter(
            character_id__in=character_ids
        ).values_list("character_id", "character_name")
    )
    destinations = dict(
        EveCorporation.objects.filter(
            corporation_id__in={
                d.destination_corporation_id
                for d in departures
                if d.destination_corporation_id
            }
        ).values_list("corporation_id", "name")
    )
    sent = survey_sent_at([d.pk for d in departures])
    joined = _joined_dates(character_ids, corporation.corporation_id)

    rows = []
    for members in group(departures):
        lead = members[0]
        flag = next(
            (
                f
                for d in members
                for f in d.flags.all()
                if f.cleared_at is None
            ),
            None,
        )
        rows.append(
            {
                "departure_ids": [d.pk for d in members],
                "character_id": lead.character_id,
                "character_name": names.get(lead.character_id) or "",
                "alt_names": [
                    names.get(d.character_id) or str(d.character_id)
                    for d in members[1:]
                ],
                "registered": lead.user_id is not None,
                "months_in_corporation": _months_in_corporation(
                    joined.get(lead.character_id, []), lead.first_missing_at
                ),
                "first_missing_at": lead.first_missing_at,
                "destination_corporation_id": lead.destination_corporation_id,
                "destination_name": destinations.get(
                    lead.destination_corporation_id
                ),
                "kind": lead.kind,
                "destination_is_npc": lead.destination_is_npc,
                "reason": lead.reason,
                "can_rejoin": lead.can_rejoin,
                "note": lead.note,
                "flag_id": flag.pk if flag else None,
                "survey_sent_at": next(
                    (sent[d.pk] for d in members if d.pk in sent), None
                ),
            }
        )
    return rows

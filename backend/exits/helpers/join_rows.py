"""Rows for the Flagged joins list on the CEO's Departures tab."""

from dataclasses import asdict

from eveonline.models import EveCharacter
from exits.helpers.history import history_for
from exits.models import FlaggedJoin


def open_join_rows(corporation) -> list[dict]:
    joins = list(
        FlaggedJoin.objects.filter(corporation=corporation, outcome="")
        .select_related("user")
        .order_by("-seen_at")
    )
    names = dict(
        EveCharacter.objects.filter(
            character_id__in=[j.character_id for j in joins]
        ).values_list("character_id", "character_name")
    )
    return [
        {
            "id": join.pk,
            "character_id": join.character_id,
            "character_name": names.get(join.character_id)
            or str(join.character_id),
            "seen_at": join.seen_at,
            "removal_expected": join.removal_expected_at is not None,
            "flags": [
                asdict(entry)
                for entry in history_for(join.user, [join.character_id])
                if entry.flag_active
            ],
        }
        for join in joins
    ]

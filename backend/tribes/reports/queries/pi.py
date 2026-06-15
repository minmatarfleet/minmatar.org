"""Planetary interaction gross ISK from corp wallet PI tax."""

from collections import defaultdict

from datetime import datetime

from django.utils import timezone

from eveonline.models import EveCharacter, EveCorporationWalletJournalEntry
from eveonline.models.characters import EvePlayer
from tribes.reports.roster import roster_character_eve_ids, roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "primary_character_name",
    "number_of_characters",
    "isk_pi_30d_estimate",
]

PI_TAX_TYPES = ("planetary_export_tax", "planetary_import_tax")


def run_pi_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    pi_tax_rate = float(params.get("pi_tax_rate", 0.01))
    start_dt = timezone.make_aware(
        datetime.combine(period.start, datetime.min.time())
    )

    if scope == ReportScope.ALLIANCE:
        char_eve_ids = None
    else:
        char_eve_ids = roster_character_eve_ids(tribe_group)
        if not char_eve_ids:
            return [], {"total_isk_pi_estimate": 0.0}, COLUMNS

    qs = EveCorporationWalletJournalEntry.objects.filter(
        ref_type__in=PI_TAX_TYPES,
        date__gte=start_dt,
    )
    end_dt = timezone.make_aware(
        datetime.combine(period.end, datetime.max.time())
    )
    qs = qs.filter(date__lte=end_dt)
    if char_eve_ids is not None:
        qs = qs.filter(first_party_id__in=char_eve_ids)

    tax_by_char: dict[int, float] = defaultdict(float)
    for entry in qs:
        if entry.first_party_id is None:
            continue
        tax_by_char[entry.first_party_id] += float(entry.amount or 0)

    chars = {
        c.character_id: c
        for c in EveCharacter.objects.filter(
            character_id__in=tax_by_char.keys()
        ).select_related("user")
    }
    gross_by_user: dict[int, float] = defaultdict(float)
    chars_by_user: dict[int, set] = defaultdict(set)

    for char_id, tax in tax_by_char.items():
        char = chars.get(char_id)
        if not char or not char.user_id:
            continue
        gross_by_user[char.user_id] += abs(tax) / pi_tax_rate
        chars_by_user[char.user_id].add(char.pk)

    if scope == ReportScope.ROSTER:
        user_ids = roster_user_ids(tribe_group)
    else:
        user_ids = set(gross_by_user.keys())

    rows = _build_user_rows(user_ids, chars_by_user, gross_by_user)
    totals = {"total_isk_pi_estimate": sum(gross_by_user.values())}
    return rows, totals, COLUMNS


def _build_user_rows(user_ids, chars_by_user, gross_by_user):
    players = {
        p.user_id: p
        for p in EvePlayer.objects.filter(user_id__in=user_ids).select_related(
            "primary_character"
        )
    }
    rows = []
    for uid in user_ids:
        pc = players.get(uid)
        name = ""
        if pc and pc.primary_character:
            name = pc.primary_character.character_name or ""
        rows.append(
            {
                "primary_character_name": name,
                "number_of_characters": len(chars_by_user.get(uid, set())),
                "isk_pi_30d_estimate": round(gross_by_user.get(uid, 0.0), 2),
            }
        )
    rows.sort(key=lambda r: r["isk_pi_30d_estimate"], reverse=True)
    return rows

"""Mining ledger reports by site user."""

from collections import defaultdict

from eveonline.models import EveCharacter, EveCharacterMiningEntry
from eveonline.models.characters import EvePlayer
from eveuniverse.models import EveMarketPrice
from tribes.reports.roster import roster_character_pks, roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "primary_character_name",
    "number_of_characters",
    "volume_m3",
    "isk_ore_market_estimate",
]


def run_mining_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    if scope == ReportScope.ROSTER:
        char_pks = roster_character_pks(tribe_group)
        if not char_pks:
            return [], _empty_totals(), COLUMNS
        entries = EveCharacterMiningEntry.objects.filter(
            character_id__in=char_pks,
            date__gte=period.start,
            date__lte=period.end,
        ).select_related("character", "character__user", "eve_type")
        user_ids = {
            e.character.user_id
            for e in entries
            if e.character and e.character.user_id
        }
        # Include roster users with zero activity
        user_ids |= roster_user_ids(tribe_group)
    else:
        entries = EveCharacterMiningEntry.objects.filter(
            date__gte=period.start,
            date__lte=period.end,
            character__user_id__isnull=False,
        ).select_related("character", "character__user", "eve_type")
        user_ids = {e.character.user_id for e in entries if e.character}

    type_ids = {e.eve_type_id for e in entries if e.eve_type_id}
    prices = {
        p.eve_type_id: p.average_price
        for p in EveMarketPrice.objects.filter(eve_type_id__in=type_ids)
    }

    vol_by_user: dict[int, float] = defaultdict(float)
    isk_by_user: dict[int, float] = defaultdict(float)
    chars_by_user: dict[int, set] = defaultdict(set)

    for entry in entries:
        uid = entry.character.user_id
        if not uid:
            continue
        vol_per = float(entry.eve_type.volume or 0) if entry.eve_type else 0
        qty = float(entry.quantity)
        volume_m3 = qty * vol_per
        price = float(prices.get(entry.eve_type_id) or 0)
        vol_by_user[uid] += volume_m3
        isk_by_user[uid] += qty * price
        chars_by_user[uid].add(entry.character_id)

    if scope == ReportScope.ROSTER:
        for uid in roster_user_ids(tribe_group):
            user_ids.add(uid)
            chars_by_user.setdefault(uid, set())

    rows = _build_user_rows(user_ids, chars_by_user, vol_by_user, isk_by_user)
    totals = {
        "total_volume_m3": sum(vol_by_user.values()),
        "total_isk_ore_market_estimate": sum(isk_by_user.values()),
    }
    return rows, totals, COLUMNS


def _empty_totals():
    return {"total_volume_m3": 0.0, "total_ore_market_estimate": 0.0}


def _build_user_rows(user_ids, chars_by_user, vol_by_user, isk_by_user):
    players = {
        p.user_id: p
        for p in EvePlayer.objects.filter(user_id__in=user_ids).select_related(
            "primary_character"
        )
    }
    # Fallback character names per user
    char_names = {}
    for uid in user_ids:
        pc = players.get(uid)
        if pc and pc.primary_character:
            char_names[uid] = pc.primary_character.character_name or ""
        else:
            c = (
                EveCharacter.objects.filter(user_id=uid)
                .order_by("character_name")
                .first()
            )
            char_names[uid] = c.character_name if c else ""

    rows = []
    for uid in user_ids:
        rows.append(
            {
                "primary_character_name": char_names.get(uid, ""),
                "number_of_characters": len(chars_by_user.get(uid, set())),
                "volume_m3": round(vol_by_user.get(uid, 0.0), 2),
                "isk_ore_market_estimate": round(isk_by_user.get(uid, 0.0), 2),
            }
        )
    rows.sort(key=lambda r: r["volume_m3"], reverse=True)
    return rows

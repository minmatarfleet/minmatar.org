"""Compute zKill-aligned dronelands combat by region (Nov 2025 – Jun 2026)."""
import ast
import json
from collections import defaultdict
from datetime import datetime

import requests
from django.db.models import F
from django.utils import timezone

from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from market.helpers.pricing import get_prices_by_type_id

DB = "production_readonly"

REGION_IDS = {
    "Etherium Reach": 10000027,
    "The Kalevala Expanse": 10000034,
    "The Spire": 10000018,
    "Perrigen Falls": 10000066,
}

MONTHS = [
    (2025, 11),
    (2025, 12),
    (2026, 1),
    (2026, 2),
    (2026, 3),
    (2026, 4),
    (2026, 5),
    (2026, 6),
]

ZKILL_DESTROYED = [
    3_410_000_000_000,
    1_240_000_000_000,
    1_760_000_000_000,
    1_470_000_000_000,
    1_860_000_000_000,
    1_120_000_000_000,
    938_640_000_000,
    692_200_000_000,
]

ZKILL_LOST = [
    803_610_000_000,
    437_750_000_000,
    497_280_000_000,
    505_270_000_000,
    431_240_000_000,
    271_490_000_000,
    190_020_000_000,
    314_410_000_000,
]

ISK_DESTROYED_MONTHLY = [
    345_813_414_159,
    478_398_512_311,
    925_261_244_915,
    691_585_269_663,
    638_610_082_208,
    265_190_928_437,
    87_446_288_666,
    54_995_218_535,
]

PERIOD_DRONELANDS_ISK_KILLS = 3_487_300_958_894
PERIOD_DRONELANDS_ISK_LOSSES = 921_347_487_752

ESI = "https://esi.evetech.net/latest"


def month_range(year: int, month: int) -> tuple[datetime, datetime]:
    start = timezone.make_aware(datetime(year, month, 1))
    if month == 12:
        end = timezone.make_aware(datetime(year + 1, 1, 1))
    else:
        end = timezone.make_aware(datetime(year, month + 1, 1))
    return start, end


def get_region_system_ids(region_id: int) -> set[int]:
    resp = requests.get(f"{ESI}/universe/regions/{region_id}/", timeout=30)
    resp.raise_for_status()
    system_ids: set[int] = set()
    for cid in resp.json()["constellations"]:
        r2 = requests.get(f"{ESI}/universe/constellations/{cid}/", timeout=30)
        r2.raise_for_status()
        system_ids.update(r2.json()["systems"])
    return system_ids


def collect_type_ids(items, out: set[int]) -> None:
    if not items:
        return
    for item in items:
        if isinstance(item, dict):
            tid = item.get("item_type_id")
            if tid:
                out.add(tid)
            collect_type_ids(item.get("items", []), out)


def parse_items(raw) -> list:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return []
    return []


def val_killmail(km, prices: dict[int, float]) -> float:
    total = prices.get(km.ship_type_id, 0)

    def walk(items) -> float:
        subtotal = 0.0
        for item in items or []:
            if isinstance(item, dict):
                tid = item.get("item_type_id")
                qty = item.get("quantity_destroyed", 0) or 0
                if tid and qty:
                    subtotal += prices.get(tid, 0) * qty
                subtotal += walk(item.get("items", []))
        return subtotal

    return total + walk(parse_items(km.items))


def system_to_region(region_systems: dict[str, set[int]], system_id: int) -> str | None:
    for name, sids in region_systems.items():
        if system_id in sids:
            return name
    return None


def main() -> None:
    region_systems = {name: get_region_system_ids(rid) for name, rid in REGION_IDS.items()}
    all_system_ids = set().union(*region_systems.values())

    alliance_ids = set(
        EveAlliance.objects.using(DB).values_list("alliance_id", flat=True)
    )
    alliance = EveAlliance.objects.using(DB).filter(name="Minmatar Fleet Alliance").first()
    char_ids = set(
        EveCharacter.objects.using(DB)
        .filter(alliance_id__in=alliance_ids)
        .values_list("character_id", flat=True)
    )
    print(f"Alliance scope: all tracked ({len(alliance_ids)} alliances, {len(char_ids)} chars)")
    if alliance:
        print(f"zKill source alliance: {alliance.name} ({alliance.ticker})")

    period_start = timezone.make_aware(datetime(2025, 11, 1))
    period_end = timezone.make_aware(datetime(2026, 6, 19))

    kill_km_ids = set(
        EveCharacterKillmailAttacker.objects.using(DB)
        .filter(
            character_id__in=char_ids,
            killmail__killmail_time__gte=period_start,
            killmail__killmail_time__lt=period_end,
        )
        .exclude(character_id=F("killmail__victim_character_id"))
        .values_list("killmail_id", flat=True)
        .distinct()
    )

    loss_km_ids = set(
        EveCharacterKillmail.objects.using(DB)
        .filter(
            victim_character_id__in=char_ids,
            killmail_time__gte=period_start,
            killmail_time__lt=period_end,
        )
        .values_list("id", flat=True)
    )

    all_km_ids = kill_km_ids | loss_km_ids
    all_type_ids: set[int] = set()
    for km in EveCharacterKillmail.objects.using(DB).filter(id__in=all_km_ids).iterator():
        all_type_ids.add(km.ship_type_id)
        collect_type_ids(parse_items(km.items), all_type_ids)

    prices = get_prices_by_type_id(list(all_type_ids))

    kills_by_month_region: dict[tuple[int, str], float] = defaultdict(float)
    losses_by_month_region: dict[tuple[int, str], float] = defaultdict(float)
    kills_by_month_dronelands: dict[int, float] = defaultdict(float)
    losses_by_month_dronelands: dict[int, float] = defaultdict(float)

    for km in EveCharacterKillmail.objects.using(DB).filter(id__in=kill_km_ids).iterator():
        month_idx = km.killmail_time.year * 12 + km.killmail_time.month - (2025 * 12 + 11)
        if month_idx < 0 or month_idx >= len(MONTHS):
            continue
        value = val_killmail(km, prices)
        region = system_to_region(region_systems, km.solar_system_id)
        if region:
            kills_by_month_region[(month_idx, region)] += value
            kills_by_month_dronelands[month_idx] += value

    for km in EveCharacterKillmail.objects.using(DB).filter(id__in=loss_km_ids).iterator():
        month_idx = km.killmail_time.year * 12 + km.killmail_time.month - (2025 * 12 + 11)
        if month_idx < 0 or month_idx >= len(MONTHS):
            continue
        value = val_killmail(km, prices)
        region = system_to_region(region_systems, km.solar_system_id)
        if region:
            losses_by_month_region[(month_idx, region)] += value
            losses_by_month_dronelands[month_idx] += value

    region_kills: dict[str, float] = defaultdict(float)
    region_losses: dict[str, float] = defaultdict(float)
    monthly_check_destroyed: list[float] = []

    for month_idx in range(len(MONTHS)):
        dronelands_kills = kills_by_month_dronelands[month_idx]
        if dronelands_kills > 0:
            for region in REGION_IDS:
                share = kills_by_month_region[(month_idx, region)] / dronelands_kills
                allocated = ISK_DESTROYED_MONTHLY[month_idx] * share
                region_kills[region] += allocated
        monthly_check_destroyed.append(sum(
            ISK_DESTROYED_MONTHLY[month_idx] * (
                kills_by_month_region[(month_idx, r)] / dronelands_kills
                if dronelands_kills > 0 else 0
            )
            for r in REGION_IDS
        ))

    for month_idx in range(len(MONTHS)):
        dronelands_losses = losses_by_month_dronelands[month_idx]
        if dronelands_losses <= 0:
            continue
        dronelands_pct = (
            ISK_DESTROYED_MONTHLY[month_idx] / ZKILL_DESTROYED[month_idx]
            if ZKILL_DESTROYED[month_idx] > 0
            else 0
        )
        month_dronelands_lost = ZKILL_LOST[month_idx] * dronelands_pct
        for region in REGION_IDS:
            share = losses_by_month_region[(month_idx, region)] / dronelands_losses
            region_losses[region] += month_dronelands_lost * share

    # Round to integers
    kills_rounded = {k: round(v) for k, v in region_kills.items()}
    losses_rounded = {k: round(v) for k, v in region_losses.items()}

    # Adjust rounding to match period totals exactly
    kills_sum = sum(kills_rounded.values())
    kills_diff = PERIOD_DRONELANDS_ISK_KILLS - kills_sum
    if kills_diff:
        top_region = max(kills_rounded, key=kills_rounded.get)
        kills_rounded[top_region] += kills_diff

    losses_sum = sum(losses_rounded.values())
    losses_diff = PERIOD_DRONELANDS_ISK_LOSSES - losses_sum
    if losses_diff:
        top_region = max(losses_rounded, key=losses_rounded.get)
        losses_rounded[top_region] += losses_diff

    result = {
        "methodology": (
            "Per month Nov 2025–Jun 2026: DB dronelands killmail ISK share by region "
            "× monthly dronelands destroyed (zKill alliance total × DB dronelands %). "
            "Losses: same regional shares applied to monthly zKill lost × dronelands %."
        ),
        "alliance": alliance.name if alliance else "Minmatar Fleet Alliance",
        "period": "2025-11-01 to 2026-06-19",
        "ISK_KILLS_BY_REGION": kills_rounded,
        "ISK_LOSSES_BY_REGION": losses_rounded,
        "sum_kills": sum(kills_rounded.values()),
        "sum_losses": sum(losses_rounded.values()),
        "target_kills": PERIOD_DRONELANDS_ISK_KILLS,
        "target_losses": PERIOD_DRONELANDS_ISK_LOSSES,
        "monthly_db_dronelands_kills": {
            str(i): round(kills_by_month_dronelands[i]) for i in range(len(MONTHS))
        },
        "monthly_db_dronelands_losses": {
            str(i): round(losses_by_month_dronelands[i]) for i in range(len(MONTHS))
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

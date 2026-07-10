"""Break down dronelands alliance losses Nov 2025 – Jun 2026 by region and ship type."""
import ast
from collections import defaultdict
from datetime import datetime

import requests
from django.utils import timezone

from eveonline.models import EveAlliance, EveCharacter, EveCharacterKillmail
from eveuniverse.models import EveType
from market.helpers.pricing import get_prices_by_type_id

DB = "production_readonly"
ESI = "https://esi.evetech.net/latest"
REGION_IDS = {
    "Etherium Reach": 10000027,
    "The Kalevala Expanse": 10000034,
    "The Spire": 10000018,
    "Perrigen Falls": 10000066,
}
MONTH_LABELS = [
    "Nov 25",
    "Dec 25",
    "Jan 26",
    "Feb 26",
    "Mar 26",
    "Apr 26",
    "May 26",
    "Jun 26",
]

CAPITAL_GROUPS = {
    "Dreadnought",
    "Carrier",
    "Supercarrier",
    "Titan",
    "Force Auxiliary",
    "Capital Industrial Ship",
    "Freighter",
    "Jump Freighter",
}
DREAD_NAMES = {
    "Revelation",
    "Phoenix",
    "Naglfar",
    "Zirnitra",
    "Moros",
    "Vehement",
    "Chemosh",
}


def get_region_system_ids(region_id: int) -> set[int]:
    resp = requests.get(f"{ESI}/universe/regions/{region_id}/", timeout=30)
    resp.raise_for_status()
    system_ids: set[int] = set()
    for cid in resp.json()["constellations"]:
        r2 = requests.get(f"{ESI}/universe/constellations/{cid}/", timeout=30)
        r2.raise_for_status()
        system_ids.update(r2.json()["systems"])
    return system_ids


def parse_items(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return []
    return []


def collect_type_ids(items, out: set[int]) -> None:
    for item in items or []:
        if isinstance(item, dict):
            tid = item.get("item_type_id")
            if tid:
                out.add(tid)
            collect_type_ids(item.get("items", []), out)


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


def main() -> None:
    region_systems = {
        name: get_region_system_ids(rid) for name, rid in REGION_IDS.items()
    }
    system_to_region = {}
    for name, sids in region_systems.items():
        for sid in sids:
            system_to_region[sid] = name

    alliance_ids = set(
        EveAlliance.objects.using(DB).values_list("alliance_id", flat=True)
    )
    char_ids = set(
        EveCharacter.objects.using(DB)
        .filter(alliance_id__in=alliance_ids)
        .values_list("character_id", flat=True)
    )

    period_start = timezone.make_aware(datetime(2025, 11, 1))
    period_end = timezone.make_aware(datetime(2026, 7, 1))

    loss_kms = list(
        EveCharacterKillmail.objects.using(DB)
        .filter(
            victim_character_id__in=char_ids,
            killmail_time__gte=period_start,
            killmail_time__lt=period_end,
            solar_system_id__in=system_to_region.keys(),
        )
        .only("id", "ship_type_id", "solar_system_id", "killmail_time", "items")
    )

    all_type_ids: set[int] = set()
    for km in loss_kms:
        all_type_ids.add(km.ship_type_id)
        collect_type_ids(parse_items(km.items), all_type_ids)

    prices = get_prices_by_type_id(list(all_type_ids))
    type_meta = {
        row.id: row
        for row in EveType.objects.filter(id__in=all_type_ids).select_related(
            "eve_group__eve_category"
        )
    }

    by_region: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    by_group: dict[str, float] = defaultdict(float)
    by_ship: dict[str, float] = defaultdict(float)
    by_bucket: dict[str, float] = defaultdict(float)

    for km in loss_kms:
        value = val_killmail(km, prices)
        region = system_to_region[km.solar_system_id]
        by_region[region] += value
        month_idx = (
            km.killmail_time.year * 12
            + km.killmail_time.month
            - (2025 * 12 + 11)
        )
        if 0 <= month_idx < 8:
            by_month[MONTH_LABELS[month_idx]] += value

        et = type_meta.get(km.ship_type_id)
        ship_name = et.name if et else str(km.ship_type_id)
        group_name = et.eve_group.name if et and et.eve_group else "Unknown"
        by_group[group_name] += value
        by_ship[ship_name] += value

        if group_name in CAPITAL_GROUPS or ship_name in DREAD_NAMES:
            if group_name == "Dreadnought" or ship_name in DREAD_NAMES:
                by_bucket["Dreadnoughts"] += value
            elif group_name in {"Carrier", "Supercarrier"}:
                by_bucket["Carriers / supers"] += value
            elif group_name == "Force Auxiliary":
                by_bucket["Force auxiliaries"] += value
            else:
                by_bucket[f"Other capitals ({group_name})"] += value
        elif group_name in {
            "Destroyer",
            "Frigate",
            "Cruiser",
            "Battlecruiser",
            "Battleship",
        }:
            by_bucket["Subcaps"] += value
        else:
            by_bucket["Other / structures / pods"] += value

    total = sum(by_region.values())
    print(f"Total dronelands losses (DB killmails): {total:,.0f} ISK ({total / 1e12:.2f}T)")
    print("\nBy region:")
    for key, value in sorted(by_region.items(), key=lambda item: -item[1]):
        print(f"  {key}: {value / 1e9:.1f}B ({100 * value / total:.1f}%)")

    print("\nBy month:")
    for month in MONTH_LABELS:
        value = by_month[month]
        if value:
            print(f"  {month}: {value / 1e9:.1f}B ({100 * value / total:.1f}%)")

    print("\nBy bucket:")
    for key, value in sorted(by_bucket.items(), key=lambda item: -item[1]):
        print(f"  {key}: {value / 1e9:.1f}B ({100 * value / total:.1f}%)")

    print("\nTop ship types:")
    for key, value in sorted(by_ship.items(), key=lambda item: -item[1])[:15]:
        print(f"  {key}: {value / 1e9:.2f}B")

    print("\nTop groups:")
    for key, value in sorted(by_group.items(), key=lambda item: -item[1])[:12]:
        print(f"  {key}: {value / 1e9:.1f}B")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Read tribe groups from production_readonly and print SQL INSERTs for
TribeGroupActivity rows appropriate to each group.

Activity selection uses ``TribeGroup.code`` (catalog keys), not name heuristics.

Usage: pipenv run python manage.py shell < scripts/tribe_activity_inserts_from_production.py
"""
from django.utils import timezone

from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id
from industry.models import IndustryOrderItemAssignment

from tribes.models import (
    TribeGroup,
    TribeGroupActivity,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)

DB = "production_readonly"
NOW = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

MANUAL_CODES = frozenset(
    {
        "pulse.technology",
        "pulse.thinkspeak",
        "pulse.readiness",
        "pulse.advocates",
        "pulse.tournaments",
        "supply.market",
        "supply.loyalty-points",
    }
)

PRODUCTION_CODES = frozenset(
    {
        "supply.subcapital-production",
        "supply.capital-production",
    }
)

CAPITALS_PREFIX = "capitals."

# Fetch all active tribe groups from production
groups = list(
    TribeGroup.objects.using(DB)
    .filter(is_active=True)
    .select_related("tribe")
    .prefetch_related(
        "requirements__asset_types__eve_type",
    )
    .order_by("tribe__name", "name")
)

# Existing activities: (tribe_group_id, activity_type, source_eve_type_id or "NULL")
existing = set()
try:
    for row in TribeGroupActivity.objects.using(DB).values_list(
        "tribe_group_id", "activity_type", "source_eve_type_id"
    ):
        existing.add((row[0], row[1], row[2]))
except Exception:
    pass


def want_activity(group, activity_type, source_eve_type_id=None):
    key = (group.pk, activity_type, source_eve_type_id)
    return key not in existing


def esc(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


def row(
    tribe_group_id,
    activity_type,
    source_eve_type_id=None,
    target_eve_type_id=None,
    description="",
):
    src = source_eve_type_id if source_eve_type_id is not None else "NULL"
    tgt = target_eve_type_id if target_eve_type_id is not None else "NULL"
    return f"({tribe_group_id}, {esc(activity_type)}, {src}, {tgt}, {esc(description)}, 1, {esc(NOW)}, {esc(NOW)})"


def get_ship_type_ids_for_group(group):
    """Ship type IDs from this group's asset requirements (qualifying ships)."""
    type_ids = []
    for req in group.requirements.using(DB).prefetch_related("asset_types__eve_type").all():
        for at in req.asset_types.all():
            if at.eve_type_id and at.eve_type:
                type_ids.append(at.eve_type_id)
    return list(dict.fromkeys(type_ids))


def get_blueprint_type_ids_for_group(group):
    """Blueprint type IDs from industry order items assigned to this group's members."""
    member_char_ids = set(
        TribeGroupMembershipCharacter.objects.using(DB)
        .filter(
            membership__tribe_group=group,
            membership__status=TribeGroupMembership.STATUS_ACTIVE,
        )
        .values_list("character_id", flat=True)
    )
    if not member_char_ids:
        return []
    item_eve_type_ids = set(
        IndustryOrderItemAssignment.objects.using(DB)
        .filter(character_id__in=member_char_ids)
        .values_list("order_item__eve_type_id", flat=True)
        .distinct()
    )
    item_eve_type_ids.discard(None)
    if not item_eve_type_ids:
        return []
    from eveuniverse.models import EveType

    blueprint_ids = []
    for eve_type in EveType.objects.using(DB).filter(id__in=item_eve_type_ids):
        try:
            bp_id = get_blueprint_or_reaction_type_id(eve_type)
            if bp_id is not None:
                blueprint_ids.append(bp_id)
        except Exception:
            continue
    return list(dict.fromkeys(blueprint_ids))


def add_combat_activities(group, inserts):
    ship_type_ids = get_ship_type_ids_for_group(group)
    targets = ship_type_ids or [None]
    for type_id in targets:
        desc_suffix = " (ship)" if type_id else ""
        if want_activity(group, TribeGroupActivity.KILLMAIL, type_id):
            inserts.append(
                (
                    group.pk,
                    row(
                        group.pk,
                        TribeGroupActivity.KILLMAIL,
                        type_id,
                        None,
                        f"Kills{desc_suffix}",
                    ),
                )
            )
        if want_activity(group, TribeGroupActivity.LOSSMAIL, type_id):
            inserts.append(
                (
                    group.pk,
                    row(
                        group.pk,
                        TribeGroupActivity.LOSSMAIL,
                        type_id,
                        None,
                        f"Losses{desc_suffix}",
                    ),
                )
            )
        if want_activity(group, TribeGroupActivity.FLEET_PARTICIPATION, type_id):
            inserts.append(
                (
                    group.pk,
                    row(
                        group.pk,
                        TribeGroupActivity.FLEET_PARTICIPATION,
                        type_id,
                        None,
                        f"Fleet{desc_suffix}",
                    ),
                )
            )


def add_production_order_activities(group, inserts):
    blueprint_ids = get_blueprint_type_ids_for_group(group)
    for bp_id in blueprint_ids:
        if want_activity(group, TribeGroupActivity.INDUSTRY_ORDER, bp_id):
            inserts.append(
                (
                    group.pk,
                    row(
                        group.pk,
                        TribeGroupActivity.INDUSTRY_ORDER,
                        bp_id,
                        None,
                        "Industry order delivery (product type)",
                    ),
                )
            )
    if want_activity(group, TribeGroupActivity.INDUSTRY_ORDER, None):
        inserts.append(
            (
                group.pk,
                row(
                    group.pk,
                    TribeGroupActivity.INDUSTRY_ORDER,
                    None,
                    None,
                    "Industry order deliveries (all)",
                ),
            )
        )


inserts = []
for g in groups:
    code = g.code or ""

    if code in MANUAL_CODES:
        continue

    if code == "supply.mining":
        if want_activity(g, TribeGroupActivity.MINING, None):
            inserts.append(
                (
                    g.pk,
                    row(g.pk, TribeGroupActivity.MINING, None, None, "Mining ledger (m³)"),
                )
            )
        continue

    if code == "supply.planetary-interaction":
        if want_activity(g, TribeGroupActivity.PLANETARY_INTERACTION, None):
            inserts.append(
                (
                    g.pk,
                    row(
                        g.pk,
                        TribeGroupActivity.PLANETARY_INTERACTION,
                        None,
                        None,
                        "PI tax",
                    ),
                )
            )
        continue

    if code in PRODUCTION_CODES:
        add_production_order_activities(g, inserts)
        continue

    if code == "pulse.fleet-commanders":
        if want_activity(g, TribeGroupActivity.FLEET_COMMANDED, None):
            inserts.append(
                (
                    g.pk,
                    row(
                        g.pk,
                        TribeGroupActivity.FLEET_COMMANDED,
                        None,
                        None,
                        "Fleets commanded",
                    ),
                )
            )
        continue

    if code.startswith(CAPITALS_PREFIX):
        add_combat_activities(g, inserts)
        continue

    if code == "supply.freighters":
        # Town hall uses freight program report; courier ingest optional for member stats
        if want_activity(g, TribeGroupActivity.COURIER_CONTRACT, None):
            inserts.append(
                (
                    g.pk,
                    row(
                        g.pk,
                        TribeGroupActivity.COURIER_CONTRACT,
                        None,
                        None,
                        "Courier deliveries (m³)",
                    ),
                )
            )
        continue

if not inserts:
    print("-- No new activities to insert.")
else:
    print("-- TribeGroupActivity INSERTs (from production_readonly)")
    print("-- Selection keyed by TribeGroup.code (see tribes/reports/registry.py).")
    print("-- Run against your writable DB (e.g. default), NOT production_readonly.")
    print("")
    print(
        "INSERT INTO tribes_tribegroupactivity "
        "(tribe_group_id, activity_type, source_eve_type_id, target_eve_type_id, description, is_active, created_at, updated_at)"
    )
    print("VALUES")
    for i, (_, v) in enumerate(inserts):
        print("  " + v + ("," if i < len(inserts) - 1 else ";"))
    print("")
    print(f"-- {len(inserts)} row(s)")

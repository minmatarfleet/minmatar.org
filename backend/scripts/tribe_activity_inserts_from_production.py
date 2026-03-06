#!/usr/bin/env python
"""
Read tribe groups from production_readonly and print SQL INSERTs for
TribeGroupActivity rows appropriate to each group.

- Killmail/lossmail/fleet: one row per qualifying ship type from the group's
  asset requirements (TribeGroupRequirementAssetType), so only that ship counts.
- Industry: one row per blueprint type that appears in industry order item
  assignments for characters in that group (from IndustryOrderItemAssignment).

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
    return list(dict.fromkeys(type_ids))  # distinct, preserve order


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
    # Order items assigned to these characters -> distinct eve_type (product)
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


inserts = []
for g in groups:
    tribe_name = (g.tribe.name or "").lower()
    group_name = (g.name or "").lower()

    # Mining-focused
    if "mining" in group_name or "mining" in tribe_name:
        if want_activity(g, TribeGroupActivity.MINING, None):
            inserts.append(
                (g.pk, row(g.pk, TribeGroupActivity.MINING, None, None, "Mining ledger (m³)"))
            )

    # Combat / capitals: use asset requirement ship types so only those ships count
    combat = any(
        x in group_name or x in tribe_name
        for x in (
            "dread",
            "carrier",
            "fax",
            "capital",
            "super",
            "titan",
            "combat",
            "pvp",
            "fleet",
        )
    )
    if combat:
        ship_type_ids = get_ship_type_ids_for_group(g)
        if ship_type_ids:
            for type_id in ship_type_ids:
                if want_activity(g, TribeGroupActivity.KILLMAIL, type_id):
                    inserts.append(
                        (g.pk, row(g.pk, TribeGroupActivity.KILLMAIL, type_id, None, "Kills (ship)"))
                    )
                if want_activity(g, TribeGroupActivity.LOSSMAIL, type_id):
                    inserts.append(
                        (g.pk, row(g.pk, TribeGroupActivity.LOSSMAIL, type_id, None, "Losses (ship)"))
                    )
                if want_activity(g, TribeGroupActivity.FLEET_PARTICIPATION, type_id):
                    inserts.append(
                        (
                            g.pk,
                            row(
                                g.pk,
                                TribeGroupActivity.FLEET_PARTICIPATION,
                                type_id,
                                None,
                                "Fleet (ship)",
                            ),
                        )
                    )
        else:
            # No ship requirements: track any ship
            if want_activity(g, TribeGroupActivity.KILLMAIL, None):
                inserts.append((g.pk, row(g.pk, TribeGroupActivity.KILLMAIL, None, None, "Kills")))
            if want_activity(g, TribeGroupActivity.LOSSMAIL, None):
                inserts.append((g.pk, row(g.pk, TribeGroupActivity.LOSSMAIL, None, None, "Losses")))
            if want_activity(g, TribeGroupActivity.FLEET_PARTICIPATION, None):
                inserts.append(
                    (
                        g.pk,
                        row(
                            g.pk,
                            TribeGroupActivity.FLEET_PARTICIPATION,
                            None,
                            None,
                            "Fleet participation",
                        ),
                    )
                )

    # Freight / hauling
    if "freight" in group_name or "hauler" in group_name or "freight" in tribe_name or "haul" in group_name:
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

    # Industry: one activity per blueprint type from orders assigned to this group
    if "industry" in group_name or "build" in group_name or "industry" in tribe_name or "production" in group_name:
        blueprint_ids = get_blueprint_type_ids_for_group(g)
        if blueprint_ids:
            for bp_id in blueprint_ids:
                if want_activity(g, TribeGroupActivity.INDUSTRY, bp_id):
                    inserts.append(
                        (
                            g.pk,
                            row(
                                g.pk,
                                TribeGroupActivity.INDUSTRY,
                                bp_id,
                                None,
                                "Industry jobs (blueprint)",
                            ),
                        )
                    )
        if want_activity(g, TribeGroupActivity.INDUSTRY, None):
            inserts.append(
                (
                    g.pk,
                    row(
                        g.pk,
                        TribeGroupActivity.INDUSTRY,
                        None,
                        None,
                        "Industry jobs (all)",
                    ),
                )
            )

    # PI
    if "pi" in group_name or "planetary" in group_name or "pi" in tribe_name:
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

    # Market
    if "market" in group_name or "market" in tribe_name:
        if want_activity(g, TribeGroupActivity.MARKET_ORDER, None):
            inserts.append(
                (g.pk, row(g.pk, TribeGroupActivity.MARKET_ORDER, None, None, "Market sales"))
            )

    # Contract (general)
    if "contract" in group_name or "contract" in tribe_name:
        if want_activity(g, TribeGroupActivity.CONTRACT, None):
            inserts.append(
                (g.pk, row(g.pk, TribeGroupActivity.CONTRACT, None, None, "Contracts posted"))
            )

if not inserts:
    print("-- No new activities to insert.")
else:
    print("-- TribeGroupActivity INSERTs (from production_readonly)")
    print("-- Killmail/lossmail/fleet: source_eve_type_id = ship from group asset requirements.")
    print("-- Industry: source_eve_type_id = blueprint types from order assignments for that group.")
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

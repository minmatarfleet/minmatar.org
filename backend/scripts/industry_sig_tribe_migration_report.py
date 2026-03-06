"""
SIG → Tribe migration report for Industry & Market (read-only, production_readonly).

Scans members of the Mining, Ship Production, Capital Production, and Freighters
SIGs and determines which characters on each account qualify for the corresponding
tribe group, based on per-SIG activity filters: mining in past 30 days, assignment
to an industry order, or delivery of a freight courier contract in the past 30 days.

All reads go through the "production_readonly" database alias — this script
NEVER writes anything to the database.

Usage (Django runscript, from backend/):
    python manage.py runscript industry_sig_tribe_migration_report

Output files written to scripts/outputs/:
    industry_sig_tribe_migration_<suffix>.txt  — per-SIG report.
    industry_sig_tribe_migration_list.json       — migration list for the executor.
"""

import json
import os
import sys
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from eveonline.models import (
    EveCharacter,
    EveCharacterMiningEntry,
    EveCorporation,
    EveCorporationContract,
)
from freight.models import FREIGHT_CORPORATION_ID
from groups.models import Sig
from industry.models import IndustryOrderItemAssignment
from tribes.helpers.requirements import characters_meeting_requirements_batch
from tribes.models import Tribe, TribeGroupMembership

DB = "production_readonly"
MINING_DAYS = 30
FREIGHT_DAYS = 30

# SIG group name (group__name) → (tribe_name, tribe_group_name)
SIG_TO_TRIBE_GROUP = {
    "SIG - Mining": ("Industry", "Mining"),
    "SIG - Ship Production": ("Industry", "Subcapital Production"),
    "SIG - Capital Production": ("Industry", "Capital Production"),
    "SIG - Freighters": ("Market", "Freighters"),
}

# For output filenames (no spaces)
SIG_TO_FILE_SUFFIX = {
    "SIG - Mining": "MINING",
    "SIG - Ship Production": "SHIP_PRODUCTION",
    "SIG - Capital Production": "CAPITAL_PRODUCTION",
    "SIG - Freighters": "FREIGHTERS",
}

MIGRATION_LIST_JSON = "industry_sig_tribe_migration_list.json"


def run():
    mining_cutoff = timezone.now() - timedelta(days=MINING_DAYS)
    freight_cutoff = timezone.now() - timedelta(days=FREIGHT_DAYS)
    scripts_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "outputs"
    )
    os.makedirs(scripts_dir, exist_ok=True)

    print("Starting Industry/Market SIG → Tribe migration report (DB=%s)..." % DB)

    # Load tribe groups from Industry and Market tribes
    tribe_groups_by_key = {}
    for tribe_name in ("Industry", "Market"):
        print("Loading %s tribe..." % tribe_name)
        try:
            tribe = Tribe.objects.using(DB).get(name=tribe_name)
        except Tribe.DoesNotExist:
            tribe = (
                Tribe.objects.using(DB)
                .filter(slug__icontains=tribe_name.lower())
                .first()
            )
        if not tribe:
            print("  WARNING: Tribe '%s' not found — skipping its SIGs." % tribe_name)
            continue
        for tg in tribe.groups.using(DB).select_related("tribe").all():
            tribe_groups_by_key[(tribe_name, tg.name)] = tg
        print("  Groups: %s" % [tg.name for tg in tribe.groups.using(DB).all()])

    # Resolve SIGs
    print("Resolving SIGs (Mining, Ship Production, Capital Production, Freighters)...")
    sigs_by_group_name = {}
    for group_name in SIG_TO_TRIBE_GROUP:
        sig = (
            Sig.objects.using(DB)
            .filter(group__name=group_name)
            .select_related("group")
            .first()
        )
        if sig:
            sigs_by_group_name[group_name] = sig
            member_count = sig.members.using(DB).count()
            print("  %s: found (%d members)" % (group_name, member_count))
        else:
            print("  WARNING: SIG '%s' not found — skipping." % group_name)

    # Freight corp for Freighters activity filter (delivered courier in past 30 days)
    try:
        freight_corp = EveCorporation.objects.using(DB).get(
            corporation_id=FREIGHT_CORPORATION_ID
        )
    except EveCorporation.DoesNotExist:
        freight_corp = None
        print("WARNING: Freight corporation (id=%s) not found — Freighters filter will exclude all."
              % FREIGHT_CORPORATION_ID)

    # Build report per SIG and write to file
    migration_list = []
    print("Output directory: %s" % scripts_dir)

    for sig_group_name, (tribe_name, tribe_group_name) in SIG_TO_TRIBE_GROUP.items():
        sig = sigs_by_group_name.get(sig_group_name)
        if not sig:
            continue

        tribe_group = tribe_groups_by_key.get((tribe_name, tribe_group_name))
        if not tribe_group:
            print(
                "WARNING: TribeGroup '%s' (tribe=%s) not found — skipping %s."
                % (tribe_group_name, tribe_name, sig_group_name)
            )
            continue

        print("")
        print(
            "Processing SIG: %s → TribeGroup: %s (id=%s)..."
            % (sig_group_name, tribe_group_name, tribe_group.pk)
        )

        tribe_group_requirements = list(
            tribe_group.requirements.prefetch_related(
                "asset_types__eve_type",
                "qualifying_skills__eve_type",
            )
            .using(DB)
            .all()
        )
        print(
            "  Loaded %d requirement(s) for batch check"
            % len(tribe_group_requirements)
        )

        if tribe_group_name == "Mining":
            print(
                "  Activity filter: any character mined in past %d days"
                % MINING_DAYS
            )
        elif tribe_group_name == "Freighters":
            print(
                "  Activity filter: any character delivered a freight courier in past %d days"
                % FREIGHT_DAYS
            )
        else:
            print(
                "  Activity filter: any character assigned to an industry order"
            )

        member_ids = list(sig.members.using(DB).values_list("id", flat=True))
        users = (
            User.objects.using(DB)
            .filter(id__in=member_ids)
            .order_by("username")
        )
        total = users.count()
        print("  Members to check: %d" % total)

        migrating = []
        not_migrating = []
        already_active_count = 0

        for i, user in enumerate(users, start=1):
            print("  [%d/%d] %s..." % (i, total, user.username))
            sys.stdout.flush()

            already_active = (
                TribeGroupMembership.objects.using(DB)
                .filter(
                    user=user,
                    tribe_group=tribe_group,
                    status=TribeGroupMembership.STATUS_ACTIVE,
                )
                .exists()
            )
            if already_active:
                already_active_count += 1
                continue

            characters = list(EveCharacter.objects.using(DB).filter(user=user))
            meeting_ids = characters_meeting_requirements_batch(
                characters,
                tribe_group,
                using=DB,
                requirements=tribe_group_requirements,
            )
            valid_chars_by_reqs = [
                c for c in characters if c.character_id in meeting_ids
            ]

            if tribe_group_name == "Mining":
                char_pks = [c.pk for c in characters]
                mined_char_pks = set(
                    EveCharacterMiningEntry.objects.using(DB)
                    .filter(
                        character_id__in=char_pks,
                        date__gte=mining_cutoff.date(),
                    )
                    .values_list("character_id", flat=True)
                    .distinct()
                )
                valid_chars = [
                    c
                    for c in valid_chars_by_reqs
                    if c.pk in mined_char_pks
                ]
            elif tribe_group_name == "Freighters":
                # Include any character that delivered a freight courier in past 30 days.
                if not freight_corp:
                    valid_chars = []
                else:
                    char_eve_ids = [c.character_id for c in characters]
                    delivered_eve_ids = set(
                        EveCorporationContract.objects.using(DB)
                        .filter(
                            corporation=freight_corp,
                            type="courier",
                            status="finished",
                            date_completed__gte=freight_cutoff,
                            acceptor_id__in=char_eve_ids,
                        )
                        .values_list("acceptor_id", flat=True)
                        .distinct()
                    )
                    valid_chars = [
                        c for c in characters if c.character_id in delivered_eve_ids
                    ]
            else:
                # Subcapital Production / Capital Production: include any character
                # that has been assigned to an order (assignment = proof of building).
                # We do not require tribe group requirements here so that builders
                # who are assigned but don't meet the full skill/asset bar still migrate.
                char_pks = [c.pk for c in characters]
                assigned_char_pks = set(
                    IndustryOrderItemAssignment.objects.using(DB)
                    .filter(character_id__in=char_pks)
                    .values_list("character_id", flat=True)
                    .distinct()
                )
                valid_chars = [c for c in characters if c.pk in assigned_char_pks]

            if valid_chars:
                migrating.append(
                    (user.username, [c.character_name for c in valid_chars])
                )
                migration_list.append(
                    {
                        "user_id": user.id,
                        "tribe_group_id": tribe_group.pk,
                        "character_ids": [c.character_id for c in valid_chars],
                    }
                )
            else:
                not_migrating.append(user.username)

        print(
            "  Already in tribe: %d | Migrating: %d | Not migrating: %d"
            % (already_active_count, len(migrating), len(not_migrating))
        )

        file_suffix = SIG_TO_FILE_SUFFIX.get(
            sig_group_name, sig_group_name.replace(" ", "_")
        )
        out_path = os.path.join(
            scripts_dir,
            "industry_sig_tribe_migration_%s.txt" % file_suffix,
        )
        with open(out_path, "w") as f:
            f.write(
                "SIG: %s  →  Tribe Group: %s\n"
                % (sig_group_name, tribe_group_name)
            )
            f.write("=" * 60 + "\n\n")
            f.write("MIGRATING (%d)\n" % len(migrating))
            f.write("-" * 40 + "\n")
            for username, char_names in migrating:
                f.write("%s: %s\n" % (username, ", ".join(char_names)))
            f.write("\nNOT MIGRATING (%d)\n" % len(not_migrating))
            f.write("-" * 40 + "\n")
            for username in not_migrating:
                f.write("%s\n" % username)
        print("  Written: %s" % out_path)

    list_path = os.path.join(scripts_dir, MIGRATION_LIST_JSON)
    with open(list_path, "w") as f:
        json.dump(migration_list, f, indent=2)
    print("")
    print(
        "Done. Total entries: %d (saved to %s)"
        % (len(migration_list), list_path)
    )

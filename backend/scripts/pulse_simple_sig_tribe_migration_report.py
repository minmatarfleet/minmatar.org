"""
Pulse / Market simple SIG → Tribe migration report (read-only, production_readonly).

Scans members of six teams/SIGs (Advocate, Readiness Divison, Technology Team,
Thinkspeak Team, Tournaments, Conversion Team) and builds a 1:1 migration list
using each user's primary character only. No activity filters.

All reads go through the "production_readonly" database alias — this script
NEVER writes anything to the database.

Usage (Django runscript, from backend/):
    python manage.py runscript pulse_simple_sig_tribe_migration_report

Output files written to scripts/outputs/:
    pulse_simple_migration_<tribe_group_name>.txt  — per-group report.
    pulse_simple_migration_list.json                — migration list for the executor.
"""

import json
import os
import sys

from django.contrib.auth.models import Group, User
from eveonline.models import EvePlayer
from groups.models import Sig
from tribes.models import Tribe, TribeGroupMembership

DB = "production_readonly"

# Source (Group name or Sig group name) → (tribe_name, tribe_group_name)
# Tournaments: use Sig with group "SIG - Tournaments"; others use auth Group
SOURCE_TO_TRIBE_GROUP = {
    "Advocate": ("Pulse", "Advocates"),
    "Readiness Divison": ("Pulse", "Readiness"),
    "Technology Team": ("Pulse", "Technology"),
    "Thinkspeak Team": ("Pulse", "Thinkspeak"),
    "SIG - Tournaments": ("Pulse", "Tournaments"),
    "Conversion Team": ("Market", "Loyalty Points"),
}

MIGRATION_LIST_JSON = "pulse_simple_migration_list.json"


def _get_primary_character(user, using):
    """Return the user's primary character from the given DB, or None."""
    player = (
        EvePlayer.objects.using(using)
        .filter(user=user)
        .select_related("primary_character")
        .first()
    )
    if player and player.primary_character_id:
        return player.primary_character
    return None


def run():
    scripts_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "outputs"
    )
    os.makedirs(scripts_dir, exist_ok=True)

    print("Starting Pulse/Market simple SIG → Tribe migration report (DB=%s)..." % DB)

    # Load tribe groups from Pulse and Market
    tribe_groups_by_key = {}
    for tribe_name in ("Pulse", "Market"):
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
            print("  WARNING: Tribe '%s' not found — skipping its groups." % tribe_name)
            continue
        for tg in tribe.groups.using(DB).select_related("tribe").all():
            tribe_groups_by_key[(tribe_name, tg.name)] = tg
        print("  Groups: %s" % [tg.name for tg in tribe.groups.using(DB).all()])

    migration_list = []
    print("Output directory: %s" % scripts_dir)

    for source_name, (tribe_name, tribe_group_name) in SOURCE_TO_TRIBE_GROUP.items():
        tribe_group = tribe_groups_by_key.get((tribe_name, tribe_group_name))
        if not tribe_group:
            print(
                "WARNING: TribeGroup '%s' (tribe=%s) not found — skipping %s."
                % (tribe_group_name, tribe_name, source_name)
            )
            continue

        # Resolve users: from Sig for Tournaments, from Group for the rest
        if source_name == "SIG - Tournaments":
            sig = Sig.objects.using(DB).filter(group__name=source_name).first()
            if not sig:
                print("WARNING: Sig for '%s' not found — skipping." % source_name)
                continue
            user_ids = list(sig.members.using(DB).values_list("id", flat=True))
            users = User.objects.using(DB).filter(id__in=user_ids).order_by("username")
        else:
            try:
                group = Group.objects.using(DB).get(name=source_name)
            except Group.DoesNotExist:
                print("WARNING: Group '%s' not found — skipping." % source_name)
                continue
            users = group.user_set.using(DB).order_by("username")

        total = users.count()
        print("")
        print(
            "Processing %s → TribeGroup: %s (id=%s), %d members..."
            % (source_name, tribe_group_name, tribe_group.pk, total)
        )

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

            primary = _get_primary_character(user, DB)
            if not primary:
                not_migrating.append((user.username, "no primary character"))
                continue

            migrating.append((user.username, primary.character_name))
            migration_list.append(
                {
                    "user_id": user.id,
                    "tribe_group_id": tribe_group.pk,
                    "character_ids": [primary.character_id],
                }
            )

        print(
            "  Already in tribe: %d | Migrating: %d | Not migrating: %d"
            % (already_active_count, len(migrating), len(not_migrating))
        )

        out_path = os.path.join(
            scripts_dir,
            "pulse_simple_migration_%s.txt" % tribe_group_name.replace(" ", "_"),
        )
        with open(out_path, "w") as f:
            f.write(
                "Source: %s  →  Tribe Group: %s\n"
                % (source_name, tribe_group_name)
            )
            f.write("=" * 60 + "\n\n")
            f.write("MIGRATING (%d)\n" % len(migrating))
            f.write("-" * 40 + "\n")
            for username, char_name in migrating:
                f.write("%s: %s\n" % (username, char_name))
            f.write("\nNOT MIGRATING (%d)\n" % len(not_migrating))
            f.write("-" * 40 + "\n")
            for username, reason in not_migrating:
                f.write("%s (%s)\n" % (username, reason))
        print("  Written: %s" % out_path)

    list_path = os.path.join(scripts_dir, MIGRATION_LIST_JSON)
    with open(list_path, "w") as f:
        json.dump(migration_list, f, indent=2)
    print("")
    print(
        "Done. Total entries: %d (saved to %s)"
        % (len(migration_list), list_path)
    )

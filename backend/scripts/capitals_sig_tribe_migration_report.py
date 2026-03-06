"""
SIG → Tribe migration report (read-only, production_readonly).

Scans members of the DREADS, CARRIERS, and FAXES SIGs and determines which
characters on each account qualify for the corresponding Capitals tribe group,
based on tribe group requirements (assets + skills, batch) and optional fleet
attendance (one batch query per user: in a qualifying ship in the past 180 days).

All reads go through the "production_readonly" database alias — this script
NEVER writes anything to the database.

Usage (Django runscript, from backend/):
    pipenv run python manage.py runscript sig_tribe_migration_report --script-path scripts

Output files written to scripts/outputs/:
    sig_tribe_migration_<SIG>.txt  — per-SIG report (migrating / not migrating).
    sig_tribe_migration_list.json  — migration list for the executor.
"""

import json
import os
import sys
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from eveonline.models import EveCharacter
from fleets.models import EveFleetInstanceMember
from groups.models import Sig
from tribes.helpers.requirements import characters_meeting_requirements_batch
from tribes.models import Tribe, TribeGroupMembership

DB = "production_readonly"
FLEET_DAYS = 180
SIG_TO_TRIBE_GROUP = {
    "DREADS": "Dreads",
    "CARRIERS": "Carriers",
    "FAXES": "Faxes",
}
MIGRATION_LIST_JSON = "sig_tribe_migration_list.json"


def run():
    CUTOFF = timezone.now() - timedelta(days=FLEET_DAYS)
    scripts_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "outputs"
    )
    os.makedirs(scripts_dir, exist_ok=True)

    print("Starting SIG → Tribe migration report (DB=%s)..." % DB)

    # Load Capitals tribe groups
    print("Loading Capitals tribe...")
    try:
        capitals_tribe = Tribe.objects.using(DB).get(name="Capitals")
    except Tribe.DoesNotExist:
        capitals_tribe = (
            Tribe.objects.using(DB).filter(slug__icontains="capital").first()
        )
        if not capitals_tribe:
            raise RuntimeError(
                "Could not find the Capitals tribe in production_readonly."
            )

    tribe_groups_by_name = {
        tg.name: tg
        for tg in capitals_tribe.groups.using(DB).select_related("tribe").all()
    }
    print("  Found tribe groups: %s" % list(tribe_groups_by_name.keys()))

    # Resolve SIGs
    print("Resolving SIGs (DREADS, CARRIERS, FAXES)...")
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

    # Build report per SIG and write to file
    migration_list = []
    print("Output directory: %s" % scripts_dir)

    for sig_group_name, tribe_group_name in SIG_TO_TRIBE_GROUP.items():
        sig = sigs_by_group_name.get(sig_group_name)
        if not sig:
            continue

        tribe_group = tribe_groups_by_name.get(tribe_group_name)
        if not tribe_group:
            print(
                "WARNING: TribeGroup '%s' not found — skipping %s."
                % (tribe_group_name, sig_group_name)
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

        qualifying_asset_type_ids = set()
        for req in tribe_group_requirements:
            for at in req.asset_types.all():
                if at.eve_type_id is not None:
                    qualifying_asset_type_ids.add(at.eve_type_id)
        qualifying_asset_type_ids = sorted(qualifying_asset_type_ids)
        if qualifying_asset_type_ids:
            print(
                "  Fleet filter: requirement asset type_ids=%s, past %d days"
                % (qualifying_asset_type_ids[:5], FLEET_DAYS)
                + (" ..." if len(qualifying_asset_type_ids) > 5 else "")
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
            if qualifying_asset_type_ids and characters:
                char_eve_ids = [c.character_id for c in characters]
                fleet_ok_ids = set(
                    EveFleetInstanceMember.objects.using(DB)
                    .filter(
                        character_id__in=char_eve_ids,
                        ship_type_id__in=qualifying_asset_type_ids,
                        eve_fleet_instance__start_time__gte=CUTOFF,
                    )
                    .values_list("character_id", flat=True)
                    .distinct()
                )
                valid_chars = [
                    c
                    for c in characters
                    if c.character_id in meeting_ids
                    and c.character_id in fleet_ok_ids
                ]
            else:
                valid_chars = [
                    c for c in characters if c.character_id in meeting_ids
                ]

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

        out_path = os.path.join(
            scripts_dir, "sig_tribe_migration_%s.txt" % sig_group_name
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

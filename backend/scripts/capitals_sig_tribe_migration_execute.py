"""
SIG → Tribe migration executor (writes to default DB).

Applies the migration list produced by sig_tribe_migration_report.py: creates
active TribeGroupMembership with qualifying characters; tribes.signals add
the user to the correct auth.Group. Uses SigRequest for approved_at/approved_by
when available.

Usage (Django runscript, from backend/):
    pipenv run python manage.py runscript sig_tribe_migration_execute --script-path scripts

Loads migration list from scripts/outputs/sig_tribe_migration_list.json (written by the report).
Optional env: SIG_TRIBE_APPROVED_BY=username (fallback approver), SIG_TRIBE_DRY_RUN=1 (preview).
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from eveonline.models import EveCharacter
from groups.models import Sig, SigRequest
from tribes.helpers.requirements import build_membership_snapshot
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
)

logger = logging.getLogger(__name__)

# TribeGroup name → SIG auth.Group name (for SigRequest lookup)
TRIBE_GROUP_TO_SIG_GROUP = {
    "Dreads": "DREADS",
    "Carriers": "CARRIERS",
    "Faxes": "FAXES",
}


def _approved_from_sig_request(
    user: User, tribe_group: TribeGroup, fallback_by, fallback_at
):
    """
    Get approved_by and approved_at from the user's approved SigRequest for the
    SIG that corresponds to this tribe group. If none found, return fallback_by and fallback_at.
    """
    sig_group_name = TRIBE_GROUP_TO_SIG_GROUP.get(tribe_group.name)
    if not sig_group_name:
        return fallback_by, fallback_at
    sig = Sig.objects.filter(group__name=sig_group_name).first()
    if not sig:
        return fallback_by, fallback_at
    sig_request = (
        SigRequest.objects.filter(user=user, sig=sig, approved=True)
        .order_by("-approved_at")
        .select_related("approved_by")
        .first()
    )
    if sig_request and sig_request.approved_at:
        return sig_request.approved_by, sig_request.approved_at
    return fallback_by, fallback_at


def _migrate_one(
    user: User,
    tribe_group: TribeGroup,
    character_ids: list,
    approved_by: Optional[User],
    approved_at: Optional[datetime],
    dry_run: bool,
) -> str:
    """
    Migrate a single (user, tribe_group, character_ids) entry.
    Returns a short status string for display.
    """
    existing = TribeGroupMembership.objects.filter(
        user=user, tribe_group=tribe_group
    ).first()

    if existing and existing.status == TribeGroupMembership.STATUS_ACTIVE:
        return "SKIP (already active member)"

    # Resolve EveCharacter objects from the default DB.
    characters = []
    missing = []
    for char_id in character_ids:
        char = EveCharacter.objects.filter(
            character_id=char_id, user=user
        ).first()
        if char:
            characters.append(char)
        else:
            missing.append(char_id)

    if missing:
        logger.warning(
            "Characters %s not found on default DB for user %s — they will be skipped.",
            missing,
            user,
        )

    if not characters:
        return "SKIP (no characters resolved on default DB)"

    resolved_ids = [c.character_id for c in characters]
    if approved_at is None:
        approved_at = timezone.now()

    if dry_run:
        names = ", ".join(c.character_name for c in characters)
        return f"DRY-RUN would create active membership with chars: [{names}]"

    with transaction.atomic():
        snapshot = build_membership_snapshot(user, tribe_group, resolved_ids)

        if existing:
            # Re-application after a prior inactive membership.
            existing.status = TribeGroupMembership.STATUS_ACTIVE
            existing.requirement_snapshot = snapshot
            existing.approved_by = approved_by
            existing.approved_at = approved_at
            existing.left_at = None
            existing.removed_by = None
            existing.history_changed_by = approved_by
            existing.save()
            membership = existing
            # Clear any stale roster entries before adding the new set.
            membership.characters.all().delete()
        else:
            membership = TribeGroupMembership(
                user=user,
                tribe_group=tribe_group,
                status=TribeGroupMembership.STATUS_ACTIVE,
                requirement_snapshot=snapshot,
                approved_by=approved_by,
                approved_at=approved_at,
            )
            membership.history_changed_by = approved_by
            membership.save()

        for char in characters:
            _, created = TribeGroupMembershipCharacter.objects.get_or_create(
                membership=membership,
                character=char,
            )
            if created:
                TribeGroupMembershipCharacterHistory.objects.create(
                    membership=membership,
                    character=char,
                    action=TribeGroupMembershipCharacterHistory.ACTION_ADDED,
                    by=approved_by,
                    at=approved_at,
                )

    names = ", ".join(c.character_name for c in characters)
    return f"MIGRATED  chars=[{names}]"


def run_sig_to_tribe_migration(
    migration_list: list,
    approved_by_user: Optional[User] = None,
    dry_run: bool = False,
) -> None:
    """
    Execute the SIG-to-tribe migration.

    Parameters
    ----------
    migration_list:
        List of dicts produced by sig_tribe_migration_report.py, each with keys:
            user_id (int), tribe_group_id (int), character_ids (list[int])
    approved_by_user:
        The User who is authorising the migration (recorded as approved_by on
        the membership). If None, the membership is created without an approver.
    dry_run:
        If True, prints what would happen without writing anything to the DB.

    Usage example
    -------------
    >>> exec(open("scripts/sig_tribe_migration_report.py").read())
    >>> exec(open("scripts/sig_tribe_migration_execute.py").read())
    >>> approved_by = User.objects.get(username="your_username")
    >>> run_sig_to_tribe_migration(MIGRATION_LIST, approved_by_user=approved_by)
    """
    if dry_run:
        print("[DRY-RUN MODE — no changes will be written]\n")

    if not migration_list:
        print("migration_list is empty — nothing to do.")
        return

    migrated = 0
    skipped = 0
    errors = 0

    for entry in migration_list:
        user_id = entry["user_id"]
        tribe_group_id = entry["tribe_group_id"]
        character_ids = entry["character_ids"]

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            print(
                f"  ERROR   user_id={user_id} not found on default DB — skipping."
            )
            errors += 1
            continue

        try:
            tribe_group = TribeGroup.objects.select_related("tribe").get(
                pk=tribe_group_id
            )
        except TribeGroup.DoesNotExist:
            print(
                f"  ERROR   tribe_group_id={tribe_group_id} not found on default DB — skipping."
            )
            errors += 1
            continue

        approved_by, approved_at = _approved_from_sig_request(
            user,
            tribe_group,
            fallback_by=approved_by_user,
            fallback_at=timezone.now(),
        )

        try:
            status = _migrate_one(
                user=user,
                tribe_group=tribe_group,
                character_ids=character_ids,
                approved_by=approved_by,
                approved_at=approved_at,
                dry_run=dry_run,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print(
                f"  ERROR   user={user.username} tribe_group={tribe_group.name}: {exc}"
            )
            logger.exception(
                "Migration failed for user=%s tribe_group=%s",
                user,
                tribe_group,
            )
            errors += 1
            continue

        if status.startswith("SKIP"):
            skipped += 1
        else:
            migrated += 1

        print(
            f"  {status}  user={user.username} (id={user_id}) "
            f"tribe_group={tribe_group.tribe.name} — {tribe_group.name}"
        )

    print(
        f"\nDone. migrated={migrated}  skipped={skipped}  errors={errors}"
        + (" [DRY-RUN]" if dry_run else "")
    )


MIGRATION_LIST_JSON = "sig_tribe_migration_list.json"


def run():
    """
    Entry point for django-extensions runscript. Loads migration list from
    scripts/sig_tribe_migration_list.json and runs the migration.
    """
    outputs_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "outputs"
    )
    list_path = os.path.join(outputs_dir, MIGRATION_LIST_JSON)
    if not os.path.isfile(list_path):
        print("No migration list found at %s" % list_path)
        print(
            "Run the report first: python manage.py runscript sig_tribe_migration_report --script-path scripts"
        )
        return
    with open(list_path) as f:
        migration_list = json.load(f)
    approved_by_username = os.environ.get("SIG_TRIBE_APPROVED_BY")
    approved_by_user = None
    if approved_by_username:
        approved_by_user = User.objects.filter(
            username=approved_by_username
        ).first()
        if not approved_by_user:
            print(
                "WARNING: SIG_TRIBE_APPROVED_BY=%s not found; using None"
                % approved_by_username
            )
    dry_run = os.environ.get("SIG_TRIBE_DRY_RUN", "").strip() in (
        "1",
        "true",
        "yes",
    )
    run_sig_to_tribe_migration(
        migration_list,
        approved_by_user=approved_by_user,
        dry_run=dry_run,
    )

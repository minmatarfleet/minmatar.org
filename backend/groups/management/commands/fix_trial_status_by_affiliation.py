"""
Set status to active for users who are trial but whose current affiliation
does not require trial (e.g. Guest, Militia). Corrects users who were marked
trial by the 0018 backfill (join date only) or who were Alliance then
switched to Guest/Militia before the signal cleared trial.
"""

from django.core.management.base import BaseCommand

from groups.models import (
    AffiliationType,
    UserAffiliation,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)


class Command(BaseCommand):
    help = (
        "Set community status to active for trial users whose current "
        "affiliation does not require trial (Guest, Militia, etc.)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report which users would be updated.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        non_trial_affiliation_ids = set(
            AffiliationType.objects.filter(requires_trial=False).values_list(
                "id", flat=True
            )
        )
        if not non_trial_affiliation_ids:
            self.stdout.write(
                "No affiliation types with requires_trial=False."
            )
            return

        trial_user_ids = set(
            UserCommunityStatus.objects.filter(status="trial").values_list(
                "user_id", flat=True
            )
        )
        user_ids_with_non_trial_affiliation = set(
            UserAffiliation.objects.filter(
                affiliation_id__in=non_trial_affiliation_ids
            ).values_list("user_id", flat=True)
        )
        to_fix = sorted(trial_user_ids & user_ids_with_non_trial_affiliation)

        if not to_fix:
            self.stdout.write(
                "No trial users with a non-requires_trial affiliation."
            )
            return

        self.stdout.write(
            f"{'Would fix' if dry_run else 'Fixing'} {len(to_fix)} user(s)."
        )

        for user_id in to_fix:
            ucs = UserCommunityStatus.objects.get(user_id=user_id)
            ua = (
                UserAffiliation.objects.filter(user_id=user_id)
                .select_related("affiliation")
                .first()
            )
            aff_name = ua.affiliation.name if ua else "?"
            if dry_run:
                self.stdout.write(
                    f"  user_id={user_id} affiliation={aff_name}"
                )
                continue
            ucs.status = UserCommunityStatus.STATUS_ACTIVE
            ucs.save(update_fields=["status"])
            UserCommunityStatusHistory.objects.create(
                user_id=user_id,
                from_status=UserCommunityStatusHistory.STATUS_TRIAL,
                to_status=UserCommunityStatusHistory.STATUS_ACTIVE,
                reason="fix_trial_status_by_affiliation management command",
                changed_by=None,
            )
            self.stdout.write(
                f"  user_id={user_id} affiliation={aff_name} -> active"
            )

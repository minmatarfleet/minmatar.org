"""Check the invariants a campaign's numbers are supposed to satisfy.

Unit tests prove a function behaves on a fixture. This walks a real campaign
and asserts the properties that have to hold across the whole pipeline, which
is where the interesting failures live: a board that disagrees with the rows
it sums, points that survived the activity behind them, a completion scored
by a code nobody confirmed.

Read-only unless --rebuild is passed.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum

from campaigns.models import (
    Campaign,
    CampaignEnlistmentCharacter,
    CampaignKillmail,
    CampaignKillmailParticipant,
    CampaignParticipantDay,
    CampaignParticipantStat,
    CampaignSiteCompletion,
    KillmailOutcome,
)
from campaigns.services import stats
from eveonline.models import FwPayoutEventCode


class Command(BaseCommand):
    help = "Assert a campaign's numbers hold together."

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="")
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="Recompute the day rows first and check they do not move.",
        )

    def handle(self, *args, **options):
        campaigns = Campaign.objects.all()
        if options["slug"]:
            campaigns = campaigns.filter(slug=options["slug"])

        failures: list[str] = []
        checked = 0

        for campaign in campaigns:
            checked += 1
            self.stdout.write(f"\n{campaign.slug} ({campaign.status})")
            if options["rebuild"]:
                failures += self._check_recompute_is_stable(campaign)
            failures += self._check_points(campaign)
            failures += self._check_boards_match_rows(campaign)
            failures += self._check_roll_ups(campaign)
            failures += self._check_outcomes(campaign)
            failures += self._check_scoring_gate(campaign)
            failures += self._check_attribution(campaign)
            failures += self._check_inclusion(campaign)

        self.stdout.write("")
        if failures:
            for failure in failures:
                self.stdout.write(self.style.ERROR(f"  FAIL {failure}"))
            self.stdout.write(
                self.style.ERROR(
                    f"{len(failures)} invariant(s) broken across "
                    f"{checked} campaign(s)"
                )
            )
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"All invariants hold across {checked} campaign(s)"
            )
        )

    # --- individual invariants -------------------------------------------

    def _ok(self, label: str) -> None:
        self.stdout.write(f"  ok   {label}")

    def _check_points(self, campaign) -> list[str]:
        negative = campaign.participant_days.filter(points__lt=0).count()
        if negative:
            return [
                f"{campaign.slug}: {negative} day rows with negative points"
            ]

        # A row with points must have something to show for them.
        empty = campaign.participant_days.filter(
            points__gt=0, active=False
        ).count()
        if empty:
            return [
                f"{campaign.slug}: {empty} inactive day rows still carrying points"
            ]

        self._ok("no negative or orphaned points")
        return []

    def _check_boards_match_rows(self, campaign) -> list[str]:
        """Every board is a sum of day rows; it must not disagree with them."""
        failures = []
        for metric, field in stats.BOARD_METRICS.items():
            board = stats.leaderboard(
                campaign, metric=metric, period="all", limit=1000
            )
            from_board = sum(row["value"] for row in board)
            from_rows = (
                campaign.participant_days.aggregate(v=Sum(field))["v"] or 0
            )
            if abs(from_board - float(from_rows)) > 0.01:
                failures.append(
                    f"{campaign.slug}: board {metric} sums {from_board} but "
                    f"the day rows sum {from_rows}"
                )
        if not failures:
            self._ok(
                f"{len(stats.BOARD_METRICS)} boards agree with their rows"
            )
        return failures

    def _check_roll_ups(self, campaign) -> list[str]:
        """CampaignParticipantStat must equal the sum of that pilot's days."""
        failures = []
        rows = campaign.participant_days.values("user_id").annotate(
            points=Sum("points"),
            kills=Sum("kills"),
            complexes=Sum("complexes"),
            active_days=Count("id", filter=Q(active=True)),
        )
        by_user = {row["user_id"]: row for row in rows}

        for stat in CampaignParticipantStat.objects.filter(campaign=campaign):
            expected = by_user.get(stat.user_id)
            if not expected:
                failures.append(
                    f"{campaign.slug}: stat row for user {stat.user_id} with "
                    "no day rows behind it"
                )
                continue
            for field in ("points", "kills", "complexes", "active_days"):
                if getattr(stat, field) != expected[field]:
                    failures.append(
                        f"{campaign.slug}: user {stat.user_id} {field} "
                        f"{getattr(stat, field)} != {expected[field]} from days"
                    )
        if not failures:
            self._ok("roll-ups equal the sum of their day rows")
        return failures

    def _check_outcomes(self, campaign) -> list[str]:
        """A kill cannot have one of ours as the victim."""
        failures = []
        bad = CampaignKillmail.objects.filter(
            campaign=campaign, outcome=KillmailOutcome.KILL
        ).filter(participants__role="victim", participants__enlisted=True)
        if bad.exists():
            failures.append(
                f"{campaign.slug}: {bad.distinct().count()} kills whose victim "
                "is one of ours"
            )

        orphan = CampaignKillmailParticipant.objects.filter(
            killmail__campaign=campaign, enlisted=True, user__isnull=True
        ).count()
        if orphan:
            failures.append(
                f"{campaign.slug}: {orphan} enlisted participants with no user"
            )

        pods = CampaignParticipantDay.objects.filter(campaign=campaign)
        pod_mails = CampaignKillmail.objects.filter(
            campaign=campaign, is_pod=True
        ).count()
        if pod_mails and not pods.exists():
            pass

        if not failures:
            self._ok("killmail outcomes are consistent")
        return failures

    def _check_scoring_gate(self, campaign) -> list[str]:
        """Nothing scores off an event code nobody confirmed."""
        confirmed = set(
            FwPayoutEventCode.objects.filter(confirmed=True).values_list(
                "event_code", flat=True
            )
        )
        leaked = CampaignSiteCompletion.objects.filter(
            campaign=campaign, scored=True
        ).exclude(event_code__in=confirmed)
        if leaked.exists():
            return [
                f"{campaign.slug}: {leaked.count()} completions scored on an "
                "unconfirmed event code"
            ]

        blocked = CampaignSiteCompletion.objects.filter(
            campaign=campaign, scored=False, event_code__in=confirmed
        )
        if blocked.exists():
            return [
                f"{campaign.slug}: {blocked.count()} completions left unscored "
                "on a code that is confirmed"
            ]

        self._ok("scoring respects the calibration table")
        return []

    def _check_attribution(self, campaign) -> list[str]:
        """Every campaign mail happened in a campaign system, in its window."""
        failures = []
        system_ids = set(
            campaign.systems.values_list("solar_system_id", flat=True)
        )
        stray = CampaignKillmail.objects.filter(campaign=campaign).exclude(
            solar_system_id__in=system_ids
        )
        if stray.exists():
            failures.append(
                f"{campaign.slug}: {stray.count()} mails outside the campaign "
                "systems"
            )

        outside = CampaignKillmail.objects.filter(campaign=campaign).exclude(
            killmail_time__range=(campaign.start_at, campaign.end_at)
        )
        if outside.exists():
            failures.append(
                f"{campaign.slug}: {outside.count()} mails outside the "
                "campaign window"
            )

        if not failures:
            self._ok("every mail is in a campaign system and window")
        return failures

    def _check_inclusion(self, campaign) -> list[str]:
        """A character counts for at most one pilot at any moment."""
        overlapping = (
            CampaignEnlistmentCharacter.objects.filter(
                enlistment__campaign=campaign, included_until__isnull=True
            )
            .values("character_id")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
        )
        if overlapping:
            return [
                f"{campaign.slug}: {len(overlapping)} characters with more "
                "than one open inclusion period"
            ]
        self._ok("no character is included twice at once")
        return []

    def _check_recompute_is_stable(self, campaign) -> list[str]:
        """Recomputing must be a no-op. Anything else means drift."""
        before = {
            (row.user_id, row.day): (row.points, row.kills, row.complexes)
            for row in campaign.participant_days.all()
        }
        days = {day for _, day in before}
        stats.materialise_days(campaign, days)

        after = {
            (row.user_id, row.day): (row.points, row.kills, row.complexes)
            for row in campaign.participant_days.all()
        }

        # The roll-ups read the day rows, so they move with them.
        stats.rebuild_stats(campaign)

        moved = [key for key in before if before[key] != after.get(key)]
        appeared = [key for key in after if key not in before]

        failures = []
        if moved:
            failures.append(
                f"{campaign.slug}: {len(moved)} day rows changed on a "
                f"recompute, e.g. {moved[0]}: "
                f"{before[moved[0]]} -> {after.get(moved[0])}"
            )
        if appeared:
            failures.append(
                f"{campaign.slug}: {len(appeared)} day rows appeared from a "
                "recompute that changed nothing"
            )
        if not failures:
            self._ok(f"recomputing {len(days)} days changed nothing")
        return failures

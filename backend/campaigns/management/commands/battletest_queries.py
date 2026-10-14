"""Count the queries behind each campaign page.

An N+1 does not fail a test, it just makes the page slower every time
somebody enlists. This measures the hot paths and fails when a page costs
more queries than it should, so the regression shows up here rather than in
production once the campaign is big.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError
from django.test.utils import CaptureQueriesContext
from django.db import connection

from campaigns.endpoints import serializers
from campaigns.models import Campaign
from campaigns.services import plan, stats

# Ceilings, not targets. A page is allowed to cost a few queries per system
# it shows; it is not allowed to cost one per pilot.
BUDGETS = {
    "index card": 40,
    "campaign detail": 60,
    "system cards": 45,
    "right now strip": 25,
    "leaderboard": 6,
    "roster + coverage": 12,
    "weekly plan": 12,
    "today's orders": 8,
}


class Command(BaseCommand):
    help = "Measure the query cost of each campaign page."

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="")

    def handle(self, *args, **options):
        campaign = (
            Campaign.objects.filter(slug=options["slug"]).first()
            if options["slug"]
            else Campaign.objects.first()
        )
        if not campaign:
            raise CommandError("No campaign to measure.")

        enlisted = campaign.enlistments.filter(status="active").count()
        systems = campaign.systems.count()
        self.stdout.write(
            f"{campaign.slug}: {enlisted} pilots, {systems} systems, "
            f"{campaign.killmails.count()} mails\n"
        )

        user = (
            campaign.enlistments.filter(status="active")
            .select_related("user")
            .first()
        )
        user = user.user if user else None

        measurements = [
            ("index card", lambda: serializers.list_item(campaign, user)),
            (
                "campaign detail",
                lambda: (
                    serializers.campaign_systems(campaign),
                    stats.campaign_totals(campaign),
                ),
            ),
            ("system cards", lambda: serializers.campaign_systems(campaign)),
            (
                "right now strip",
                lambda: (
                    stats.active_recently(campaign),
                    stats.system_heat(campaign),
                    plan.orders_for(campaign, user),
                ),
            ),
            ("leaderboard", lambda: stats.leaderboard(campaign, limit=25)),
            (
                "roster + coverage",
                lambda: (
                    serializers.roster_rows(campaign),
                    serializers.coverage_by_hour(campaign),
                ),
            ),
            ("weekly plan", lambda: stats.week_summary(campaign)),
            ("today's orders", lambda: plan.orders_for(campaign, user)),
        ]

        failures = []
        for label, call in measurements:
            with CaptureQueriesContext(connection) as captured:
                started = time.monotonic()
                call()
                elapsed = (time.monotonic() - started) * 1000

            count = len(captured)
            budget = BUDGETS[label]
            verdict = "ok  " if count <= budget else "OVER"
            if count > budget:
                failures.append(f"{label}: {count} queries, budget {budget}")

            self.stdout.write(
                f"  {verdict} {label:<20} {count:>4} queries  "
                f"{elapsed:>7.0f} ms"
            )

        self.stdout.write("")
        if failures:
            for failure in failures:
                self.stdout.write(self.style.ERROR(f"  OVER {failure}"))
            raise SystemExit(1)

        self.stdout.write(
            self.style.SUCCESS("Every page is inside its query budget")
        )

"""Confirm what a Faction Warfare payout event code actually is.

Codes ship unconfirmed because the notification text is rendered from the
code client-side, so we cannot tell a Rendezvous Point from a beacon without
somebody running one and saying so. An unconfirmed code is stored and shown
but never scored; confirming it here makes the sites already recorded count.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from campaigns.models import SiteKind
from campaigns.services.sites import rescore_completions
from eveonline.models import FwPayoutEventCode

SITE_KINDS = [choice[0] for choice in SiteKind.choices]


class Command(BaseCommand):
    help = "Confirm a FW payout event code and rescore what it covers."

    def add_arguments(self, parser):
        parser.add_argument("event_code", type=int)
        parser.add_argument(
            "--site-kind",
            required=True,
            choices=SITE_KINDS,
            help="What running this site actually is.",
        )
        parser.add_argument("--label", default="")
        parser.add_argument(
            "--by", default="", help="Who confirmed it, and how."
        )
        parser.add_argument(
            "--unconfirm",
            action="store_true",
            help="Put a code back into the unscored state.",
        )

    def handle(self, *args, **options):
        code = options["event_code"]
        row = FwPayoutEventCode.objects.filter(event_code=code).first()
        if not row:
            raise CommandError(
                f"Event code {code} has never been seen. Run the payout poll "
                "first, or add it in the admin."
            )

        row.site_kind = options["site_kind"]
        row.label = options["label"] or row.label
        row.confirmed = not options["unconfirm"]
        row.confirmed_by = options["by"]
        row.confirmed_at = timezone.now() if row.confirmed else None
        row.save()

        result = rescore_completions(event_code=code)
        state = "confirmed" if row.confirmed else "unconfirmed"
        self.stdout.write(
            self.style.SUCCESS(
                f"Event {code} is now {state} as {row.site_kind}; "
                f"{result['changed']} completions rescored."
            )
        )

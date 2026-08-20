"""Instantiate a survey campaign from the code-defined survey.

Usage:
    python manage.py seed_survey_campaign --open
    python manage.py seed_survey_campaign --year 2027 --quarter 1 --open
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from surveys.constants import STATUS_DRAFT, STATUS_OPEN
from surveys.definitions import (
    default_definition,
    definition_keys,
    get_definition,
)
from surveys.models import SurveyCampaign


class Command(BaseCommand):
    help = "Create a survey campaign from the code-defined survey."

    def add_arguments(self, parser):
        parser.add_argument("--def", dest="definition_key", default=None)
        parser.add_argument("--year", type=int, default=None)
        parser.add_argument("--quarter", type=int, default=None)
        parser.add_argument("--open", action="store_true", dest="open_now")

    def handle(self, *args, **options):
        key = options["definition_key"]
        if key:
            definition = get_definition(key)
            if key not in definition_keys():
                raise CommandError(
                    f"Unknown definition '{key}'. Known: {definition_keys()}"
                )
        else:
            definition = default_definition()

        # Default the period to the current calendar quarter.
        now = timezone.now()
        year = options["year"] or now.year
        quarter = options["quarter"] or ((now.month - 1) // 3 + 1)

        if SurveyCampaign.objects.filter(year=year, quarter=quarter).exists():
            raise CommandError(
                f"A campaign already exists for {year} Q{quarter}."
            )

        open_now = options["open_now"]
        campaign = SurveyCampaign.objects.create(
            year=year,
            quarter=quarter,
            definition_key=definition.key,
            title=f"{year} Q{quarter} Community Survey",
            status=STATUS_OPEN if open_now else STATUS_DRAFT,
            opens_at=timezone.now() if open_now else None,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Created campaign #{campaign.pk}: {campaign.title} "
                f"({campaign.get_status_display()})"
            )
        )

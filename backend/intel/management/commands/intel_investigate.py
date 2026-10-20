"""Investigate one group now and print what the scorer makes of it.

manage.py intel_investigate alliance 99004901
manage.py intel_investigate alliance 99010022 --score
"""

from django.core.management.base import BaseCommand

from intel.affiliations import resolve, score
from intel.affiliations.investigate import investigate
from intel.models import IntelEntity


class Command(BaseCommand):
    help = "Read a group's zKill history now, then score it."

    def add_arguments(self, parser):
        parser.add_argument("kind", choices=["alliance", "corporation"])
        parser.add_argument("eve_id", type=int)
        parser.add_argument(
            "--score",
            action="store_true",
            help="Also suggest its bloc (needs its partners investigated).",
        )

    def handle(self, *args, **options):
        entity, _ = IntelEntity.objects.get_or_create(
            kind=options["kind"], eve_id=options["eve_id"]
        )
        stats = investigate(entity)
        entity.refresh_from_db()
        self.stdout.write(f"{entity.name or entity.eve_id}: {stats}")
        months = score.window()
        kills = score.sampled_kills(entity.pk, months)
        found = sorted(
            score.partners(entity, months).values(), key=lambda p: -p.shared
        )[:10]
        for partner in found:
            share = partner.shared / kills if kills else 0
            self.stdout.write(
                f"  {partner.kind} {partner.eve_id}: {partner.shared} shared "
                f"({share:.0%}), {len(partner.months)} months, "
                f"{partner.against} against"
            )
        if options["score"]:
            row = score.score_group(entity, months)
            resolve.invalidate()
            self.stdout.write(
                f"Suggested: {row} {row.evidence if row else ''}"
            )

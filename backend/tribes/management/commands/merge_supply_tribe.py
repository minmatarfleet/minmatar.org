"""
Merge Industry + Market into Supply (prod-safe Discord path).

Dry-run by default. Pass --apply to write DB changes and call Discord.

Prod::

    docker compose -f docker-compose-prod.yml exec app \\
      python3 manage.py merge_supply_tribe --dry-run

    docker compose -f docker-compose-prod.yml exec app \\
      python3 manage.py merge_supply_tribe --apply
"""

from django.core.management.base import BaseCommand, CommandError

from tribes.helpers.merge_supply_tribe import run_merge_supply_tribe


class Command(BaseCommand):
    help = (
        "Merge Industry + Market tribes into Supply: rename auth/Discord roles "
        "in place, reparent groups, merge Contracts+Market Orders into Market, "
        "migrate auth members via user.groups add/remove (Discord signals)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist changes and call Discord APIs. Without this, dry-run only.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Plan only (default). Mutually informational with --apply.",
        )

    def handle(self, *args, **options):
        apply = bool(options["apply"])
        if options["dry_run"] and apply:
            raise CommandError("Pass only one of --dry-run or --apply.")

        log = run_merge_supply_tribe(apply=apply)
        for line in log.lines:
            self.stdout.write(line)
        if apply:
            self.stdout.write(
                self.style.SUCCESS("merge_supply_tribe apply complete.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run only. Re-run with --apply to persist + Discord."
                )
            )

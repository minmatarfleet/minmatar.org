"""
Merge Capital Production and Subcapital Production into Production.

Idempotent. Safe to re-run when a Discord role update failed mid-merge.

Prod::

    docker compose -f docker-compose-prod.yml exec app \\
      python3 manage.py merge_production_groups
"""

from django.apps import apps
from django.core.management.base import BaseCommand

from tribes.helpers.merge_production_groups import merge_production_groups


class Command(BaseCommand):
    help = (
        "Merge Capital Production and Subcapital Production into one "
        "Production group, keeping every member, character and history row."
    )

    def handle(self, *args, **options):
        lines = merge_production_groups(apps)
        for line in lines:
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS("Production merge complete."))

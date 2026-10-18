"""Requests per desktop version over the last days (app/client_versions.py).

Run before removing or renaming a field the desktop reads: a version that
still reads it and still shows up here would break.
"""

from django.core.management.base import BaseCommand

from app.client_versions import counts


class Command(BaseCommand):
    help = "Requests per X-Minmatar-Client version, per day"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **options):
        for day, clients in counts(options["days"]).items():
            self.stdout.write(day)
            for client, requests in sorted(clients.items()):
                self.stdout.write(f"  {client}: {requests}")

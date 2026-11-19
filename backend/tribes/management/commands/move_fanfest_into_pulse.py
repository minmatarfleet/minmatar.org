"""
Move Fanfest under Pulse, keeping every member.

Idempotent. Safe to re-run when a Discord role update failed mid-move.

Prod::

    docker compose -f docker-compose-prod.yml exec app \\
      python3 manage.py move_fanfest_into_pulse
"""

from django.apps import apps
from django.core.management.base import BaseCommand

from discord.client import DiscordClient
from tribes.helpers.move_fanfest_into_pulse import move_fanfest_into_pulse


class Command(BaseCommand):
    help = (
        "Move the Fanfest tribe into the Pulse tribe as one group and "
        "keep every member, character and Discord role."
    )

    def handle(self, *args, **options):
        lines = move_fanfest_into_pulse(apps, discord_client=DiscordClient())
        for line in lines:
            self.stdout.write(line)
        self.stdout.write(self.style.SUCCESS("Fanfest move complete."))

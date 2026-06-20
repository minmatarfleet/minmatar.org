from __future__ import annotations

from django.core.management.base import BaseCommand

from feed.helpers.affiliations import (
    apply_killmail_affiliations,
    populate_character_affiliations_from_esi,
    refresh_character_affiliation,
)
from feed.models import FeedCharacterAffiliation, FeedKillmail


class Command(BaseCommand):
    help = "Apply killmail affiliations and optionally ESI populate/refresh"

    def add_arguments(self, parser):
        parser.add_argument(
            "--populate",
            action="store_true",
            help="ESI-check all unchecked character rows after killmail apply",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="ESI-refresh all resolved character rows after killmail apply",
        )

    def handle(self, *args, **options):
        character_ids: set[int] = set()
        for raw, killmail_time in FeedKillmail.objects.values_list(
            "raw_killmail", "killmail_time"
        ).iterator():
            apply_killmail_affiliations(raw, confirmed_at=killmail_time)
            for attacker in raw.get("attackers") or []:
                char_id = attacker.get("character_id")
                if char_id:
                    character_ids.add(char_id)
            victim = raw.get("victim") or {}
            victim_char = victim.get("character_id")
            if victim_char:
                character_ids.add(victim_char)

        unchecked_ids = set(
            FeedCharacterAffiliation.objects.filter(
                esi_checked_at__isnull=True,
            ).values_list("character_id", flat=True)
        )

        populated = 0
        refreshed = 0
        if options["populate"]:
            populated = populate_character_affiliations_from_esi(
                sorted(unchecked_ids)
            )

        if options["refresh"]:
            for character_id in character_ids:
                if refresh_character_affiliation(character_id):
                    refreshed += 1

        self.stdout.write(
            self.style.SUCCESS(
                "FeedCharacterAffiliation rows: "
                f"{FeedCharacterAffiliation.objects.count()} "
                f"(populated: {populated}, refreshed: {refreshed})"
            )
        )

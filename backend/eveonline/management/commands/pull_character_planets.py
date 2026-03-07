"""
Pull PI (planetary interaction) from ESI for a character and show outputs.

Default: BearThatFarms (by character name or username bearthatfarms/bearthatcares).
Requires the character to have an ESI token with esi-planets.manage_planets.v1.

Usage:
  python manage.py pull_character_planets
  python manage.py pull_character_planets --character-name BearThatFarms
  python manage.py pull_character_planets --character-id 12345678
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from eveonline.helpers.characters.planets import update_character_planets
from eveonline.models import (
    EveCharacter,
    EveCharacterPlanet,
    EveCharacterPlanetOutput,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Pull PI from ESI for a character (default: BearThatFarms) and show outputs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--character-name",
            type=str,
            default="BearThatFarms",
            help="Character name (partial match). Default: BearThatFarms.",
        )
        parser.add_argument(
            "--character-id",
            type=int,
            help="EVE character ID (overrides --character-name if set).",
        )

    def handle(self, *args, **options):
        character_id = options.get("character_id")
        character_name = options.get("character_name", "BearThatFarms")

        if character_id is not None:
            character = EveCharacter.objects.filter(
                character_id=character_id
            ).first()
            if not character:
                self.stdout.write(
                    self.style.ERROR(f"Character id={character_id} not found.")
                )
                return
        else:
            character = EveCharacter.objects.filter(
                character_name__icontains=character_name
            ).first()
            if not character:
                user = (
                    User.objects.filter(
                        username__icontains=character_name.lower().replace(
                            " ", ""
                        )
                    ).first()
                    or User.objects.filter(
                        username__icontains="bearthatcares"
                    ).first()
                )
                if user:
                    character = EveCharacter.objects.filter(user=user).first()
            if not character:
                self.stdout.write(
                    self.style.ERROR(
                        f"Character or user matching '{character_name}' not found."
                    )
                )
                return

        self.stdout.write(
            f"Character: {character.character_name} (character_id={character.character_id})"
        )

        count = update_character_planets(character.character_id)
        self.stdout.write(self.style.SUCCESS(f"Synced {count} planet(s)."))

        planets = EveCharacterPlanet.objects.filter(
            character=character
        ).order_by("planet_id")
        self.stdout.write(f"Planets: {planets.count()}")
        for p in planets:
            outputs = EveCharacterPlanetOutput.objects.filter(
                planet=p
            ).select_related("eve_type")
            self.stdout.write(
                f"  Planet {p.planet_id} ({p.planet_type}): "
                f"{outputs.count()} output(s)"
            )
            for o in outputs:
                ext = (
                    f", extractors={o.extractor_count}"
                    if o.extractor_count is not None
                    else ""
                )
                fac = (
                    f", factories={o.factory_count}"
                    if o.factory_count is not None
                    else ""
                )
                self.stdout.write(
                    f"    - {o.eve_type.name} ({o.output_type}): "
                    f"daily={o.daily_quantity}{ext}{fac}"
                )

#!/usr/bin/env python
"""
Pull PI (planetary interaction) for BearThatFarms and verify harvest/production data.
Run from backend: pipenv run python manage.py runscript pull_pi_bearthatfarms
"""
from django.contrib.auth import get_user_model

from eveonline.helpers.characters.planets import update_character_planets
from eveonline.models import (
    EveCharacter,
    EveCharacterPlanet,
    EveCharacterPlanetOutput,
)

User = get_user_model()


def run():
    # Find BearThatFarms (character name or user bearthatfarms/bearthatcares)
    character = EveCharacter.objects.filter(
        character_name__icontains="BearThatFarms"
    ).first()
    if not character:
        user = (
            User.objects.filter(username__icontains="bearthatfarms").first()
            or User.objects.filter(username__icontains="bearthatcares").first()
        )
        if user:
            character = EveCharacter.objects.filter(user=user).first()
    if not character:
        print("BearThatFarms character/user not found.")
        return

    print(
        f"Character: {character.character_name} (character_id={character.character_id})"
    )

    # Pull PI from ESI
    count = update_character_planets(character.character_id)
    print(f"Synced {count} planet(s).")

    # Show planets and outputs (with extractor_count / factory_count)
    planets = EveCharacterPlanet.objects.filter(character=character).order_by(
        "planet_id"
    )
    print(f"Planets: {planets.count()}")
    for p in planets:
        outputs = EveCharacterPlanetOutput.objects.filter(
            planet=p
        ).select_related("eve_type")
        print(
            f"  Planet {p.planet_id} ({p.planet_type}): {outputs.count()} output(s)"
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
            print(
                f"    - {o.eve_type.name} ({o.output_type}): daily={o.daily_quantity}{ext}{fac}"
            )

from datetime import datetime

from django.contrib.auth.models import User
from django.db.models import signals

from eveonline.models import EveAlliance, EveCorporation, EveCharacter
from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetAudience,
    EveFleetLocation,
)


def setup_test_data():
    """Setup test data in the database"""

    print("Setting up test data...")
    disable_signals()
    user = setup_users()
    char = setup_orgs(user)
    setup_fleets(char)
    print("Complete.")


def disable_signals():
    """Disable signals prior to making database changes"""
    print("Disabling signals")

    signals.post_save.disconnect(
        sender=EveCharacter,
        dispatch_uid="populate_eve_character_public_data",
    )
    signals.post_save.disconnect(
        sender=EveCharacter,
        dispatch_uid="populate_eve_character_private_data",
    )
    signals.post_save.disconnect(
        sender=EveAlliance,
        dispatch_uid="eve_alliance_post_save",
    )
    signals.post_save.disconnect(
        sender=EveFleet,
        dispatch_uid="update_fleet_schedule_on_save",
    )


def setup_users() -> User:
    user, _ = User.objects.get_or_create(
        username="testerdude",
    )
    return user


def setup_orgs(user: User) -> EveCharacter:
    alliance, _ = EveAlliance.objects.get_or_create(
        alliance_id=12345,
        name="FL33T",
        ticker="FL33T",
    )
    megacorp, _ = EveCorporation.objects.get_or_create(
        corporation_id=23456,
    )
    megacorp.alliance = alliance
    megacorp.name = "MegaCorp"
    megacorp.ticker = "Mega"
    megacorp.save()

    main, _ = EveCharacter.objects.get_or_create(
        character_id=123456,
        defaults={
            "character_name": "Test Pilot",
        },
    )
    setup_char(main, megacorp, user, True)
    main.save()

    alt, _ = EveCharacter.objects.get_or_create(
        character_id=123457,
        defaults={
            "character_name": "Alt Pilot",
        },
    )
    setup_char(alt, megacorp, user, False)
    alt.save()

    return main


def setup_char(
    char: EveCharacter, corp: EveCorporation, user: User, is_primary: bool
):
    char.corporation = corp
    char.alliance = corp.alliance
    char.user = user
    char.is_primary = is_primary


def setup_fleets(fc: EveCharacter) -> EveFleet:
    rabble, _ = EveFleetAudience.objects.get_or_create(
        name="Rabble",
    )
    homebase, _ = EveFleetLocation.objects.get_or_create(
        location_name="Homebase",
        defaults={
            "location_id": 1234,
            "solar_system_id": 2000,
            "solar_system_name": "Home",
        },
    )

    fleet, _ = EveFleet.objects.get_or_create(
        id=123,
        defaults={
            "type": "strategic",
            "start_time": datetime.now(),
        },
    )
    fleet.description = "Whelp fleet"
    fleet.created_by = fc.user
    fleet.status = "active"
    fleet.disable_motd = True
    fleet.audience = rabble
    fleet.location = homebase
    fleet.save()

    instance, _ = EveFleetInstance.objects.get_or_create(
        id=123,
        defaults={
            "eve_fleet": fleet,
        },
    )
    instance.boss_id = fc.character_id
    instance.save()

    EveFleetInstanceMember.objects.get_or_create(
        eve_fleet_instance=instance,
        character_id=fc.character_id,
        defaults={
            "character_name": fc.character_name,
            "ship_type_id": 1000,
            "solar_system_id": 2000,
            "wing_id": 3000,
            "squad_id": 3100,
        },
    )

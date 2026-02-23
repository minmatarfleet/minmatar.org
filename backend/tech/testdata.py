import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import signals
from django.utils import timezone

from authentication import make_test_user

from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveLocation,
)
from eveuniverse.models import EveFaction
from fittings.models import EveFitting
from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetAudience,
)

logger = logging.getLogger("authentication")


def setup_test_data():
    """Setup test data in the database"""

    logger.info("Setting up test data...")
    disable_signals()
    user = setup_users()
    char = setup_orgs(user)
    setup_fittings()
    setup_fleets(char)
    logger.info("Complete.")


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
    user1 = make_test_user(1, "AdminDude", True)
    make_test_user(2, "TesterDude", False)
    return user1


def setup_orgs(user: User) -> EveCharacter:
    EveLocation.objects.get_or_create(
        location_name="Homebase",
        defaults={
            "location_id": 1234,
            "solar_system_id": 2000,
            "solar_system_name": "Home",
            "short_name": "Home",
            "staging_active": True,
            "freight_active": True,
            "market_active": True,
            "prices_active": True,
        },
    )
    fl33t, _ = EveAlliance.objects.get_or_create(
        alliance_id=99011978,
        name="FL33T",
        ticker="FL33T",
    )
    megacorp, _ = EveCorporation.objects.get_or_create(
        corporation_id=23456,
    )
    megacorp.alliance = fl33t
    megacorp.name = "MegaCorp"
    megacorp.ticker = "Mega"
    megacorp.save()

    main, _ = EveCharacter.objects.get_or_create(
        character_id=123456,
        defaults={
            "character_name": "Test Pilot",
        },
    )
    setup_char(main, megacorp, user)
    main.save()
    megacorp.ceo = main
    megacorp.save()

    logger.info(
        "Setting primary character for %s to %s",
        user.username,
        main.character_name,
    )
    set_primary_character(user, main)

    alt, _ = EveCharacter.objects.get_or_create(
        character_id=123457,
        defaults={
            "character_name": "Alt Pilot",
        },
    )
    setup_char(alt, megacorp, user)
    alt.save()

    return main


def setup_char(char: EveCharacter, corp: EveCorporation, user: User):
    char.corporation_id = corp.corporation_id
    char.alliance_id = corp.alliance.alliance_id if corp.alliance else None
    char.user = user
    char.esi_token_level = "Basic"


def setup_fittings():
    EveFitting.objects.get_or_create(
        name="AC Rifter",
        defaults={
            "ship_id": 587,
            "description": "AC Rifter",
            "eft_format": """[Rifter, AC Rifter]

Damage Control II
400mm Rolled Tungsten Compact Plates
Multispectrum Coating II
Counterbalanced Compact Gyrostabilizer

5MN Quad LiF Restrained Microwarpdrive
Initiated Compact Warp Scrambler
Fleeting Compact Stasis Webifier

150mm Light Prototype Automatic Cannon
150mm Light Prototype Automatic Cannon
150mm Light Prototype Automatic Cannon

Small Ancillary Current Router I
Small Trimark Armor Pump I
Small Trimark Armor Pump I


Nanite Repair Paste x5
Fusion S x2000
Republic Fleet EMP S x720
Republic Fleet Fusion S x720
Republic Fleet Phased Plasma S x720
""",
        },
    )


def setup_fleets(fc: EveCharacter) -> EveFleet:
    rabble, _ = EveFleetAudience.objects.get_or_create(
        name="Rabble",
    )
    homebase, _ = EveLocation.objects.get_or_create(
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
            "start_time": timezone.now(),
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

    historical, _ = EveFleet.objects.get_or_create(
        id=124,
        defaults={
            "type": "strategic",
            "start_time": timezone.now() - timedelta(days=7),
        },
    )
    historical.description = "Whelped fleet"
    historical.created_by = fc.user
    historical.status = "complete"
    historical.disable_motd = True
    historical.audience = rabble
    historical.location = homebase
    historical.save()


def minmil_faction():
    faction, _ = EveFaction.objects.get_or_create(
        id=500002,
        defaults={
            "is_unique": True,
            "militia_corporation_id": 1000182,
            "name": "Minmatar Republic",
            "description": "MinMil",
            "size_factor": 5,
            "station_count": 595,
            "station_system_count": 306,
        },
    )
    return faction

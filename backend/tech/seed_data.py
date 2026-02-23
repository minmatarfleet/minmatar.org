import logging
from django.contrib.auth.models import Group
from django.db import transaction
from django.conf import settings
import requests
from structures.models import EveStructure
from eveonline.models import (
    EveAlliance,
    EveCorporation,
    EveCharacter,
    EveTag,
    EsiClient,
)
from posts.models import EveTag as PostsEveTag
from market.models import EveMarketContractExpectation
from groups.models import AffiliationType, EveCorporationGroup, Team, Sig
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.models import EveFleetAudience, EveLocation

logger = logging.getLogger(__name__)


def seed_database_for_development():
    """
    Seed the database with initial data for development purposes.
    This is targets at a setup with a dev discord server instance and bot, as well as esi application integration.
    This includes creating core alliances, corporations, locations, market expectations, and more.
    """
    logger.info("Starting database seeding for development")

    # Verify we have required settings
    if not settings.ESI_SSO_CLIENT_ID or not settings.ESI_SSO_CLIENT_SECRET:
        logger.error("ESI Client ID and Secret Key must be set in settings")
        return False
    if not settings.DISCORD_BOT_TOKEN or not settings.DISCORD_GUILD_ID:
        logger.error("Discord Bot Token and Guild ID must be set in settings")
        return False

    # Verify database is empty
    if EveCharacter.objects.exists() or EveAlliance.objects.exists():
        logger.error("Database is not empty. Please reset before seeding")
        return False

    try:
        with transaction.atomic():
            seed_core_alliances()
            seed_affiliations()
            seed_corporation_groups()
            seed_locations()
            seed_fleet_audiences()
            sync_production_fittings()
            seed_market_expectations()
            sync_tag_definitions()
            sync_post_tags()
            sync_teams_and_sigs()

        logger.info("Database seeding completed successfully")
        return True
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        return False


@transaction.atomic
def seed_core_alliances():
    """Create core alliances and their corporations"""
    logger.info("Seeding core alliances")

    alliances = [
        {"alliance_id": 99011978},
        {"alliance_id": 99012009},
    ]

    for alliance_data in alliances:
        alliance, created = EveAlliance.objects.get_or_create(
            alliance_id=alliance_data["alliance_id"]
        )
        if created:
            logger.info(f"Created alliance: {alliance.name}")

    # Fetch and create corporations for each alliance
    for alliance in EveAlliance.objects.all():
        logger.info(f"Fetching corporations for alliance {alliance.name}")
        esi_response = EsiClient(None).get_alliance_corporations(
            alliance.alliance_id
        )

        if not esi_response.success():
            logger.error(
                f"Failed to fetch corporations for {alliance.name}: {esi_response.response_code}"
            )
            continue

        corporations = esi_response.results()
        for corporation_id in corporations:
            corporation, created = EveCorporation.objects.get_or_create(
                corporation_id=corporation_id
            )
            corporation.populate()
            if created:
                logger.info(f"Created corporation: {corporation.name}")

    logger.info("Core alliances seeded successfully")


@transaction.atomic
def seed_affiliations():
    """Create affiliations for core alliances"""
    logger.info("Seeding affiliations for core alliances")

    fl33t_alliance = EveAlliance.objects.filter(alliance_id=99011978).first()
    alliance_group = Group.objects.filter(name="Alliance").first()

    if not fl33t_alliance:
        logger.error("FL33T alliance not found")
        return
    if not alliance_group:
        logger.error("Alliance group not found")
        return

    affiliation_type, created = AffiliationType.objects.get_or_create(
        name="AreYouFl33t",
        defaults={
            "description": "AreYouFl33t",
            "group": alliance_group,
            "priority": 1,
        },
    )

    affiliation_type.alliances.add(fl33t_alliance)

    if created:
        logger.info(f"Created affiliation type: {affiliation_type.name}")
    logger.info("Affiliations seeded successfully")


@transaction.atomic
def seed_corporation_groups():
    """Link corporation groups to their respective corporations"""
    logger.info("Seeding corporation groups")

    linked_count = 0
    for group in Group.objects.filter(name__startswith="Corp "):
        corporation_name = group.name.replace("Corp ", "").strip()
        eve_corporation = EveCorporation.objects.filter(
            name=corporation_name
        ).first()

        if eve_corporation:
            _, created = EveCorporationGroup.objects.get_or_create(
                group=group,
                corporation=eve_corporation,
            )
            if created:
                logger.info(
                    f"Linked group {group.name} to corporation {eve_corporation.name}"
                )
                linked_count += 1

    logger.info(
        f"Corporation groups seeded successfully ({linked_count} links created)"
    )


@transaction.atomic
def seed_locations():
    """Create basic staging locations and structures"""
    logger.info("Seeding locations")

    corporation = EveCorporation.objects.get(name="Soltech Armada")
    structure_id = 1049037316814

    structure, created = EveStructure.objects.get_or_create(
        id=structure_id,
        defaults={
            "system_id": 30002538,
            "system_name": "Vard",
            "type_id": 35833,  # Fortizar
            "type_name": "Fortizar",
            "name": "Rickety Roost",
            "reinforce_hour": 12,
            "fuel_expires": None,
            "state": "active",
            "state_timer_start": None,
            "state_timer_end": None,
            "fitting": None,
            "corporation": corporation,
            "is_valid_staging": True,
        },
    )

    location, location_created = EveLocation.objects.get_or_create(
        location_id=structure_id,
        defaults={
            "location_name": "Vard - Rickety Roost",
            "solar_system_id": 30002538,
            "solar_system_name": "Vard",
            "short_name": "the roost",
            "region_id": 10000030,
            "market_active": True,
            "prices_active": True,
            "freight_active": True,
            "staging_active": True,
            "structure": structure,
        },
    )

    if created:
        logger.info(f"Created structure: {structure.name}")
    if location_created:
        logger.info(f"Created location: {location.location_name}")

    logger.info("Locations seeded successfully")


@transaction.atomic
def seed_market_expectations():
    """Create market expectations for doctrine fittings"""
    logger.info("Seeding market expectations")

    location = EveLocation.objects.filter(
        location_name="Vard - Rickety Roost"
    ).first()
    if not location:
        logger.error("Rickety Roost location not found")
        return

    expectations_created = 0
    for doctrine_fitting in EveDoctrineFitting.objects.all():
        _, created = EveMarketContractExpectation.objects.get_or_create(
            fitting=doctrine_fitting.fitting,
            location=location,
            defaults={"quantity": 5},
        )
        if created:
            expectations_created += 1

    logger.info(
        f"Market expectations seeded successfully ({expectations_created} created)"
    )


@transaction.atomic
def seed_fleet_audiences():
    """Create fleet audiences for alliance pings"""
    logger.info("Seeding fleet audiences")

    alliance_group = Group.objects.filter(name="Alliance").first()
    if not alliance_group:
        logger.error("Alliance group not found")
        return

    discord_channels = get_discord_channels()  # Call the function!

    alliance_pings_channel_id = None
    fleet1_voice_channel = None

    for channel in discord_channels:
        if channel["name"] == "alliance-pings" and channel["type"] == "text":
            alliance_pings_channel_id = channel["id"]
        if channel["name"] == "Fleet 1" and channel["type"] == "voice":
            fleet1_voice_channel = channel["id"]

    if not alliance_pings_channel_id or not fleet1_voice_channel:
        logger.error(
            "Discord channels for alliance pings or fleet voice not found"
        )
        return
    fleet_audience, created = EveFleetAudience.objects.get_or_create(
        name="Alliance",
        defaults={
            "discord_channel_id": alliance_pings_channel_id,
            "discord_channel_name": "alliance-pings",
            "discord_voice_channel_name": "Fleet 1",
            "discord_voice_channel": fleet1_voice_channel,
            "add_to_schedule": True,
            "hidden": False,
        },
    )

    fleet_audience.groups.add(alliance_group)

    if created:
        logger.info(f"Created fleet audience: {fleet_audience.name}")
    logger.info("Fleet audiences seeded successfully")


@transaction.atomic
def sync_production_fittings():
    """Sync fittings and doctrines from production API"""
    logger.info("Syncing production fittings")

    # Sync fittings
    response = requests.get(
        "https://api.minmatar.org/api/fittings/", timeout=10
    )
    response.raise_for_status()
    fittings_data = response.json()

    fittings_created = 0
    for fitting in fittings_data:
        _, created = EveFitting.objects.get_or_create(
            id=fitting["id"],
            defaults={
                "name": fitting["name"],
                "ship_id": fitting["ship_id"],
                "description": fitting.get("description", ""),
                "eft_format": fitting.get("eft_format", ""),
                "minimum_pod": fitting.get("minimum_pod", ""),
                "recommended_pod": fitting.get("recommended_pod", ""),
            },
        )
        if created:
            fittings_created += 1

    # Sync doctrines
    response = requests.get(
        "https://api.minmatar.org/api/doctrines/", timeout=10
    )
    response.raise_for_status()
    doctrines_data = response.json()

    doctrines_created = 0
    for doctrine in doctrines_data:
        doctrine_id = doctrine["id"]
        composition_response = requests.get(
            f"https://api.minmatar.org/api/doctrines/{doctrine_id}/composition",
            timeout=10,
        )
        composition_response.raise_for_status()
        composition_response.json()

        doctrine_obj, created = EveDoctrine.objects.get_or_create(
            id=doctrine["id"],
            defaults={
                "name": doctrine["name"],
                "type": doctrine["type"],
                "description": doctrine.get("description", ""),
            },
        )
        if created:
            doctrines_created += 1

        # Process fitting types
        fitting_types = [
            ("primary_fittings", "primary"),
            ("support_fittings", "support"),
            ("secondary_fittings", "secondary"),
        ]

        for fitting_key, role in fitting_types:
            for fitting_data in doctrine.get(fitting_key, []):
                fitting = EveFitting.objects.get(id=fitting_data["id"])
                EveDoctrineFitting.objects.get_or_create(
                    role=role,
                    doctrine=doctrine_obj,
                    fitting=fitting,
                    defaults={"ideal_ship_count": 1},
                )

    logger.info(
        f"Production fittings synced successfully ({fittings_created} fittings, {doctrines_created} doctrines created)"
    )


@transaction.atomic
def sync_tag_definitions():
    """Sync character tag definitions from production API"""
    logger.info("Syncing tag definitions")

    response = requests.get(
        "https://api.minmatar.org/api/eveonline/characters/tags", timeout=10
    )
    response.raise_for_status()
    tags_data = response.json()

    tags_created = 0
    for tag in tags_data:
        _, created = EveTag.objects.get_or_create(
            id=tag["id"],
            defaults={
                "title": tag["title"],
                "description": tag.get("description", ""),
                "image_name": tag.get("image_name", ""),
            },
        )
        if created:
            tags_created += 1

    logger.info(
        f"Tag definitions synced successfully ({tags_created} created)"
    )


@transaction.atomic
def sync_post_tags():
    """Sync blog post tags from production API"""
    logger.info("Syncing post tags")

    response = requests.get(
        "https://api.minmatar.org/api/blog/tags", timeout=10
    )
    response.raise_for_status()
    tags_data = response.json()

    tags_created = 0
    for tag in tags_data:
        _, created = PostsEveTag.objects.get_or_create(
            id=tag["tag_id"], defaults={"tag": tag["tag"]}
        )
        if created:
            tags_created += 1

    logger.info(f"Post tags synced successfully ({tags_created} created)")


@transaction.atomic
def sync_teams_and_sigs():
    """Sync teams and sigs from production API with Discord channel mapping"""
    logger.info("Syncing teams and sigs")

    # Manual mapping data: team/sig name -> (group_name, discord_channel_name)
    mappings = {
        "People Team": ("People Team", None),
        "Conversion Team": ("Conversion Team", "conversion"),
        "Supply Team": ("Supply Team", "supply"),
        "Technology Team": ("Technology Team", "technology"),
        "Thinkspeak Team": ("Thinkspeak Team", "thinkspeak"),
        "FC Team": ("FC", "fcs"),
        "Internal Affairs": ("Internal Affairs", "internal-affairs"),
        "External Affairs": ("External Affairs", "external-affairs"),
        "Readiness Division": (
            "Readiness Divison",
            "readiness",
        ),  # Note: typo in group name
        "Advocate": ("Advocate", None),
        "Black Ops": ("SIG - Black Ops", "blackops"),
        "FAXES": ("FAXES", "faxes"),
        "DREADS": ("DREADS", "dreads"),
        "CARRIERS": ("CARRIERS", "carriers"),
        "TOURNAMENTS": ("SIG - Tournaments", "tournaments"),
    }

    discord_channels = get_discord_channels()

    # Process teams
    teams_response = requests.get(
        "https://api.minmatar.org/api/teams/", timeout=10
    )
    teams_response.raise_for_status()
    teams_data = teams_response.json()

    teams_processed = 0
    for team in teams_data:
        if process_entity(team, "team", mappings, discord_channels):
            teams_processed += 1

    # Process sigs
    sigs_response = requests.get(
        "https://api.minmatar.org/api/sigs/", timeout=10
    )
    sigs_response.raise_for_status()
    sigs_data = sigs_response.json()

    sigs_processed = 0
    for sig in sigs_data:
        if process_entity(sig, "sig", mappings, discord_channels):
            sigs_processed += 1

    logger.info(
        f"Teams and sigs synced successfully ({teams_processed}/{len(teams_data)} teams, {sigs_processed}/{len(sigs_data)} sigs)"
    )


def process_entity(entity_data, entity_type, mappings, discord_channels):
    """Process a single team or sig entity"""
    entity_name = entity_data["name"]
    entity_id = entity_data["id"]

    if entity_name not in mappings:
        logger.warning(
            f"No mapping found for {entity_type} '{entity_name}', skipping"
        )
        return False

    group_name, discord_channel_name = mappings[entity_name]

    try:
        group = Group.objects.get(name=group_name) if group_name else None
    except Group.DoesNotExist:
        logger.error(
            f"Group '{group_name}' not found for {entity_type} '{entity_name}', skipping"
        )
        return False

    discord_channel_id = find_discord_channel_id(
        discord_channel_name, discord_channels
    )

    if discord_channel_name and not discord_channel_id:
        logger.warning(
            f"Discord channel '{discord_channel_name}' not found for {entity_type} '{entity_name}'"
        )

    entity_class = Team if entity_type == "team" else Sig
    _, created = entity_class.objects.get_or_create(
        id=entity_id,
        defaults={
            "name": entity_name,
            "description": entity_data.get("description", ""),
            "image_url": entity_data.get("image_url", ""),
            "discord_channel_id": discord_channel_id,
            "group": group,
        },
    )

    if created:
        logger.info(f"Created {entity_type}: {entity_name}")
    return True


def find_discord_channel_id(channel_name, discord_channels):
    """Find Discord channel ID by name (case insensitive)"""
    if not channel_name:
        return None

    for channel in discord_channels:
        if (
            channel["name"].lower() == channel_name.lower()
            and channel["type"] == "text"
        ):
            return channel["id"]
    return None


def get_discord_channels():
    """Get all channels from Discord server"""
    session = requests.Session()
    access_token = settings.DISCORD_BOT_TOKEN
    guild_id = settings.DISCORD_GUILD_ID

    response = session.get(
        f"https://discord.com/api/v9/guilds/{guild_id}/channels",
        headers={"Authorization": f"Bot {access_token}"},
        timeout=10,
    )
    response.raise_for_status()
    response_data = response.json()

    type_map = {0: "text", 2: "voice", 4: "category", 13: "stage", 15: "forum"}
    return [
        {
            "name": channel["name"],
            "type": type_map.get(channel["type"], "unknown"),
            "id": channel["id"],
        }
        for channel in response_data
    ]

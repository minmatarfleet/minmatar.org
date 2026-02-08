import json
import logging
import math
from datetime import datetime, timedelta

from django.utils import timezone
from django.conf import settings

from app.celery import app

from discord.client import DiscordClient
from eveonline.client import EsiClient, esi_for
from eveonline.models import EveAlliance, EveCorporation

from .models import EveStructure, EveStructureManager, EveStructurePing
from structures.helpers import (
    parse_structure_notification,
    is_new_event,
    discord_message_for_ping,
    parse_esi_time,
)

discord = DiscordClient()
logger = logging.getLogger(__name__)


LOW_FUEL_EXCLUDED_TYPES = [
    "Metenox Moon Drill",
    "Ansiblex Jump Gate",
    "Ansiblex Jump Bridge",
]


@app.task
def update_structures():
    allied_alliances = EveAlliance.objects.all()
    EveStructure.objects.exclude(
        corporation__alliance__in=allied_alliances,
    ).delete()

    for corporation in EveCorporation.objects.filter(
        alliance__in=allied_alliances,
    ):
        update_corporation_structures.delay(corporation.corporation_id)


@app.task
def update_corporation_structures(corporation_id: int):
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    logger.info("Updating structures for corporation %s", corporation)
    if not corporation.ceo:
        logger.debug(
            "Corporation %s has no CEO",
            corporation.name,
        )
        return

    # required_scopes = ["esi-corporations.read_structures.v1"]

    # token = Token.get_token(corporation.ceo.character_id, required_scopes)
    # if token:
    #     logger.debug("Fetching structures for corporation %s", corporation)
    #     response = esi.client.Corporation.get_corporations_corporation_id_structures(
    #         corporation_id=corporation.corporation_id,
    #         token=token.valid_access_token(),
    #     ).results()

    esi = esi_for(corporation.ceo)

    response = esi.get_corp_structures(corporation.corporation_id)
    if response.success():
        known_structure_ids = []
        for structure in response.results():
            logger.info("Updating structure %s", structure["name"])
            logger.debug("Structure details %s", structure)
            system = esi.get_solar_system(structure["system_id"])
            structure_type = esi.get_eve_type(structure["type_id"])
            corporation = EveCorporation.objects.get(
                corporation_id=structure["corporation_id"]
            )
            if EveStructure.objects.filter(
                id=structure["structure_id"]
            ).exists():
                logger.debug(
                    "Updating existing structure %s", structure["name"]
                )
                eve_structure = EveStructure.objects.get(
                    id=structure["structure_id"]
                )
                eve_structure.state = structure["state"]
                eve_structure.state_timer_start = structure.get(
                    "state_timer_start"
                )
                eve_structure.state_timer_end = structure.get(
                    "state_timer_end"
                )
                eve_structure.fuel_expires = structure.get("fuel_expires")
                eve_structure.name = structure["name"]
                services = structure.get("services")
                eve_structure.fitting = (
                    json.dumps(services, indent=2) if services else None
                )
                eve_structure.save()
            else:
                logger.debug("Creating new structure %s", structure["name"])
                services = structure.get("services")
                eve_structure = EveStructure.objects.create(
                    id=structure["structure_id"],
                    system_id=structure["system_id"],
                    system_name=system.name,
                    type_id=structure["type_id"],
                    type_name=structure_type.name,
                    name=structure["name"],
                    reinforce_hour=structure["reinforce_hour"],
                    state=structure["state"],
                    state_timer_start=structure.get("state_timer_start"),
                    state_timer_end=structure.get("state_timer_end"),
                    fuel_expires=structure.get("fuel_expires"),
                    fitting=(
                        json.dumps(services, indent=2) if services else None
                    ),
                    corporation=corporation,
                )

            known_structure_ids.append(eve_structure.id)

        # delete structures that are no longer in the response
        structures = EveStructure.objects.filter(corporation=corporation)
        for structure in structures:
            if structure.id not in known_structure_ids:
                logger.info("Deleting structure %s", structure.name)
                structure.delete()
    else:
        logger.warning(
            "Error %d accessing structures for %s",
            response.response_code,
            corporation.name,
        )
    # else:
    #     logger.info(
    #         "Corporation %s does not have valid CEO token",
    #         corporation,
    #     )


@app.task
def process_structure_notifications(
    current_minute: datetime | None = None,
):
    if current_minute is None:
        current_minute = timezone.now().minute

    total_found = 0
    total_new = 0

    for esm in structure_managers_for_minute(current_minute):
        logger.info(
            "Fetching notifications for %s in %s",
            esm.character.character_name,
            esm.corporation.name,
        )
        found, new = fetch_structure_notifications(esm)
        total_found += found
        total_new += new

    if total_found > 0:
        logger.info(
            "Found a total of %d structure notifications (%d new)",
            total_found,
            total_new,
        )

    return total_found, total_new


def fetch_structure_notifications(manager: EveStructureManager):
    response = EsiClient(manager.character).get_character_notifications()
    if not response.success():
        logger.error(
            "Error %d fetching notifications for %s : %s",
            response.response_code,
            manager.character.character_name,
            response.response,
        )
        return 0, 0

    manager.last_polled = timezone.now()
    manager.save()

    combat_types = [
        "StructureDestroyed",
        "StructureLostArmor",
        "StructureLostShields",
        "StructureUnderAttack",
    ]

    total_found = 0
    total_new = 0
    for notification in response.results():
        if notification["type"] in combat_types:
            data = parse_structure_notification(notification["text"])
            event, created = EveStructurePing.objects.get_or_create(
                notification_id=notification["notification_id"],
                defaults={
                    "notification_type": notification["type"],
                    "summary": data["data"],
                    "structure_id": data["structure_id"],
                    "reported_by": manager.character,
                    "text": notification["text"],
                    "event_time": parse_esi_time(notification["timestamp"]),
                },
            )
            if created:
                logger.info(
                    "Found new notification %d (%s) %s - would ping? %s",
                    event.notification_id,
                    notification["timestamp"],
                    event.notification_type,
                    is_new_event(event),
                )
                if is_new_event(event):
                    send_discord_structure_notification(
                        event, settings.DISCORD_STRUCTURE_PINGS_CHANNEL_ID
                    )
                    total_new += 1

            total_found += 1

    return (total_found, total_new)


def structure_managers_for_minute(current_minute: int):
    mod_minute = current_minute % 10
    return EveStructureManager.objects.filter(poll_time=mod_minute)


def setup_structure_managers(corp, chars):
    logger.info(
        "Setting up %d structure managers for %s", len(chars), corp.name
    )
    interval = math.floor(10 / len(chars))
    minute = 0

    # Set up new ESMs for corp
    for char in chars:
        EveStructureManager.objects.create(
            corporation=corp,
            character=char,
            poll_time=minute,
        )
        minute += interval


def send_discord_structure_notification(ping: EveStructurePing, channel: int):
    discord.create_message(
        channel_id=channel,
        message=discord_message_for_ping(ping),
    )
    ping.discord_success = True
    ping.save()


@app.task
def notify_low_fuel_structures():
    """
    Notify DISCORD_STRUCTURE_PINGS_CHANNEL_ID of structures with less than
    7 days of fuel, excluding Metenox Moon Drill and Ansiblex Jump Gate. Runs daily.
    """
    now = timezone.now()
    cutoff = now + timedelta(days=7)
    low_fuel = (
        EveStructure.objects.filter(
            fuel_expires__isnull=False,
            fuel_expires__lt=cutoff,
        )
        .exclude(type_name__in=LOW_FUEL_EXCLUDED_TYPES)
        .order_by("fuel_expires")
    )
    structures = list(low_fuel)
    if not structures:
        logger.info("No structures with less than 7 days fuel to notify")
        return

    lines = ["**Structures with less than 7 days of fuel**"]
    for s in structures:
        delta = s.fuel_expires - now
        days = max(0, delta.days)
        if days == 0:
            days_text = "<1 day"
        else:
            days_text = f"{days} day{'s' if days != 1 else ''}"
        lines.append(
            f"• **{s.name}** ({s.type_name}) – {s.system_name} – {days_text}"
        )
    message = "\n".join(lines)
    channel_id = settings.DISCORD_STRUCTURE_PINGS_CHANNEL_ID
    discord.create_message(channel_id=channel_id, message=message)
    logger.info(
        "Notified %s of %d low-fuel structure(s)",
        channel_id,
        len(structures),
    )

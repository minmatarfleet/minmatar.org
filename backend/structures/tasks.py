import json
import logging
from datetime import datetime, timedelta

from django.utils import timezone
from django.conf import settings

from app.celery import app

from discord.client import DiscordClient
from eveonline.client import EsiClient, esi_for
from eveonline.helpers.corporations import get_director_with_scope
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from eveonline.utils import get_esi_downtime_countdown

from .models import EveStructure, EveStructurePing
from structures.helpers import (
    parse_structure_notification,
    is_new_event,
    discord_message_for_ping,
    parse_esi_time,
    ensure_timer_from_reinforcement_notification,
    get_characters_with_notification_scope_for_structure_corps,
)

discord = DiscordClient()
logger = logging.getLogger(__name__)


LOW_FUEL_EXCLUDED_TYPES = [
    "Metenox Moon Drill",
    "Ansiblex Jump Gate",
    "Ansiblex Jump Bridge",
]

SCOPE_STRUCTURES = ["esi-corporations.read_structures.v1"]


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
    countdown = get_esi_downtime_countdown()
    if countdown > 0:
        update_corporation_structures.apply_async(
            args=[corporation_id],
            countdown=countdown,
        )
        logger.info(
            "Deferring structure update for corp %s by %s s (ESI downtime 11:00–11:15 UTC)",
            corporation_id,
            countdown,
        )
        return

    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    logger.info("Updating structures for corporation %s", corporation)

    character = get_director_with_scope(corporation, SCOPE_STRUCTURES)
    if not character:
        logger.debug(
            "Corporation %s has no director/CEO with structures scope, skipping",
            corporation.name,
        )
        return

    esi = esi_for(character)
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


def _notification_characters_for_minute(current_minute: int):
    """Characters with read_notifications in corps that have structures, in this minute's bucket (0–9)."""
    mod = current_minute % 10
    chars = get_characters_with_notification_scope_for_structure_corps()
    return [c for c in chars if c.character_id % 10 == mod]


@app.task
def process_structure_notifications(
    current_minute: datetime | None = None,
):
    """Schedule notification fetch for each director (with read_notifications) in corps that have structures."""
    countdown = get_esi_downtime_countdown()
    if countdown > 0:
        process_structure_notifications.apply_async(countdown=countdown)
        logger.info(
            "Deferring structure notification run by %s s (ESI downtime 11:00–11:15 UTC)",
            countdown,
        )
        return 0, 0

    if current_minute is None:
        current_minute = timezone.now().minute

    characters = list(_notification_characters_for_minute(current_minute))
    for i, character in enumerate(characters):
        delay = i % 600  # spread over 10 min
        fetch_structure_notifications_for_character.apply_async(
            args=[character.character_id],
            countdown=delay,
        )
    if characters:
        logger.info(
            "Scheduled notification fetch for %d character(s) with read_notifications",
            len(characters),
        )
    return len(characters), 0


@app.task(rate_limit="1/m")
def fetch_structure_notifications_for_character(character_id: int):
    """Fetch notifications for one character with read_notifications in a corp that has structures."""
    countdown = get_esi_downtime_countdown()
    if countdown > 0:
        fetch_structure_notifications_for_character.apply_async(
            args=[character_id],
            countdown=countdown,
        )
        return 0, 0

    try:
        character = EveCharacter.objects.get(character_id=character_id)
    except EveCharacter.DoesNotExist:
        logger.warning("Character %s not found", character_id)
        return 0, 0

    if not character.corporation_id:
        logger.warning("Character %s has no corporation", character_id)
        return 0, 0

    # Only poll if this character is still in a corp that has structures and has the scope
    if (
        not get_characters_with_notification_scope_for_structure_corps()
        .filter(character_id=character_id)
        .exists()
    ):
        logger.debug(
            "Character %s no longer in a structure corp with read_notifications, skipping",
            character_id,
        )
        return 0, 0

    return fetch_structure_notifications(character)


def fetch_structure_notifications(character):
    response = EsiClient(character).get_character_notifications()
    if not response.success():
        logger.error(
            "Error %d fetching notifications for %s : %s",
            response.response_code,
            character.character_name,
            response.response,
        )
        return 0, 0

    combat_types = [
        "StructureDestroyed",
        "StructureLostArmor",
        "StructureLostShields",
        "StructureUnderAttack",
        "OrbitalAttacked",
        "OrbitalReinforced",
    ]

    total_found = 0
    total_new = 0
    esi = EsiClient(character)
    corp = EveCorporation.objects.filter(
        corporation_id=character.corporation_id
    ).first()
    corporation_name = corp.name if corp else "Unknown"
    alliance_name = (
        corp.alliance.name
        if corp and corp.alliance_id and corp.alliance
        else None
    )

    def resolve_system_name(system_id: int) -> str:
        try:
            solar_system = esi.get_solar_system(system_id)
            return solar_system.name
        except Exception:
            return f"System {system_id}"

    for notification in response.results():
        if notification["type"] in combat_types:
            data = parse_structure_notification(notification["text"])
            event, created = EveStructurePing.objects.get_or_create(
                notification_id=notification["notification_id"],
                defaults={
                    "notification_type": notification["type"],
                    "summary": data["data"],
                    "structure_id": data["structure_id"],
                    "reported_by": character,
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

            # When we have a reinforcement with a timer, add/update EveStructureTimer
            ensure_timer_from_reinforcement_notification(
                notification["type"],
                data,
                corporation_name=corporation_name,
                alliance_name=alliance_name,
                system_name_resolver=resolve_system_name,
            )

            total_found += 1

    return (total_found, total_new)


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

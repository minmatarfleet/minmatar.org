import json
import logging
from datetime import timedelta

from django.utils import timezone
from django.conf import settings

from app.celery import app
from app.models import get_or_create_active

from discord.client import DiscordClient
from eveonline.client import esi_for
from eveonline.helpers.corporations import get_director_with_scope
from eveonline.models import (
    EveAlliance,
    EveCharacterNotification,
    EveCorporation,
)
from eveonline.utils import get_esi_downtime_countdown

from .models import EveStructure, EveStructurePing
from structures.helpers import (
    parse_structure_notification,
    is_new_event,
    discord_message_for_ping,
)

discord = DiscordClient()
logger = logging.getLogger(__name__)


LOW_FUEL_EXCLUDED_TYPES = [
    "Metenox Moon Drill",
    "Ansiblex Jump Gate",
    "Ansiblex Jump Bridge",
]

SCOPE_STRUCTURES = ["esi-corporations.read_structures.v1"]


@app.task(expires=30 * 60, cooldown=30 * 60)
def update_structures():
    # Tracked scope (every EveAlliance row), not just FL33T + BUILD: we keep
    # structures for every alliance an admin has added to the site.
    allied_alliances = EveAlliance.objects.all()
    EveStructure.objects.exclude(
        corporation__alliance__in=allied_alliances,
    ).delete()

    queued = 0
    for corporation in EveCorporation.objects.filter(
        alliance__in=allied_alliances,
    ):
        # Most corps have no director who granted the scope; queueing them
        # only to skip filled the queue.
        if get_director_with_scope(corporation, SCOPE_STRUCTURES):
            update_corporation_structures.delay(corporation.corporation_id)
            queued += 1
    logger.info("Queued structure updates for %d corporation(s)", queued)
    return queued


# ESI caches corporation structures for an hour and beat polls hourly.
@app.task(expires=50 * 60, cooldown=30 * 60)
def update_corporation_structures(corporation_id: int):
    if get_esi_downtime_countdown() > 0:
        # The next hourly run picks this corporation up.
        logger.info(
            "Skipping structure update for corp %s (ESI downtime 11:00–11:15 UTC)",
            corporation_id,
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
            services = structure.get("services")
            structure_defaults = {
                "system_id": structure["system_id"],
                "system_name": system.name,
                "type_id": structure["type_id"],
                "type_name": structure_type.name,
                "name": structure["name"],
                "reinforce_hour": structure["reinforce_hour"],
                "state": structure["state"],
                "state_timer_start": structure.get("state_timer_start"),
                "state_timer_end": structure.get("state_timer_end"),
                "fuel_expires": structure.get("fuel_expires"),
                "fitting": (
                    json.dumps(services, indent=2) if services else None
                ),
                "corporation": corporation,
            }
            eve_structure, created = get_or_create_active(
                EveStructure,
                id=structure["structure_id"],
                defaults=structure_defaults,
            )
            if created:
                logger.debug("Creating new structure %s", structure["name"])
            else:
                logger.debug(
                    "Updating existing structure %s", structure["name"]
                )
                for key, value in structure_defaults.items():
                    setattr(eve_structure, key, value)
                eve_structure.save()

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


STRUCTURE_COMBAT_TYPES = [
    "StructureDestroyed",
    "StructureLostArmor",
    "StructureLostShields",
    "StructureUnderAttack",
    "OrbitalAttacked",
    "OrbitalReinforced",
]

# How far back each run looks for stored notifications it has not turned
# into pings. Generous, so a stalled worker catches up; is_new_event keeps
# old events out of Discord.
STRUCTURE_NOTIFICATION_LOOKBACK = timedelta(hours=2)


@app.task(expires=60, cooldown=50)
def process_structure_notifications():
    """Turn stored structure-combat notifications into pings.

    ``eveonline.tasks.notifications`` fetches every character's
    notifications; this only reads the ones from characters in a corporation
    that owns one of our structures.
    """
    since = timezone.now() - STRUCTURE_NOTIFICATION_LOOKBACK
    corporation_ids = list(
        EveStructure.objects.values_list(
            "corporation__corporation_id", flat=True
        ).distinct()
    )
    if not corporation_ids:
        return 0, 0

    rows = (
        EveCharacterNotification.objects.filter(
            type__in=STRUCTURE_COMBAT_TYPES,
            created_at__gte=since,
            character__corporation_id__in=corporation_ids,
        )
        .exclude(
            notification_id__in=EveStructurePing.objects.values(
                "notification_id"
            )
        )
        .select_related("character")
        .order_by("timestamp")
    )

    total_found = 0
    total_new = 0
    for row in rows:
        total_found += 1
        if store_structure_ping(row):
            total_new += 1
    return total_found, total_new


def store_structure_ping(row: EveCharacterNotification) -> bool:
    """Store one structure notification as a ping. True when it was posted."""
    data = parse_structure_notification(row.text)
    event, created = EveStructurePing.objects.get_or_create(
        notification_id=row.notification_id,
        defaults={
            "notification_type": row.type,
            "summary": data["data"],
            "structure_id": data["structure_id"],
            "reported_by": row.character,
            "text": row.text,
            "event_time": row.timestamp,
        },
    )
    if not created:
        return False
    logger.info(
        "Found new notification %d (%s) %s - would ping? %s",
        event.notification_id,
        row.timestamp,
        event.notification_type,
        is_new_event(event),
    )
    if not is_new_event(event):
        return False
    send_discord_structure_notification(
        event, settings.DISCORD_STRUCTURE_PINGS_CHANNEL_ID
    )
    return True


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

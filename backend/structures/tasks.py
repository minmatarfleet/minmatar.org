import logging
import math
from datetime import datetime

from django.utils import timezone
from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveSolarSystem, EveType

from app.celery import app
from eveonline.client import EsiClient
from eveonline.models import EveCorporation

from .models import EveStructure, EveStructureManager, EveStructurePing
from structures.helpers import parse_structure_notification

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


@app.task
def update_structures():
    for corporation in EveCorporation.objects.filter(
        alliance__name__in=[
            "Minmatar Fleet Alliance",
            "Minmatar Fleet Associates",
        ]
    ):
        update_corporation_structures.delay(corporation.corporation_id)


@app.task
def update_corporation_structures(corporation_id: int):
    corporation = EveCorporation.objects.get(corporation_id=corporation_id)
    logger.info("Updating structures for corporation %s", corporation)
    if (
        corporation.ceo
        and corporation.ceo.token
        and not corporation.ceo.esi_suspended
    ):
        logger.debug(
            "Corporation %s has token for CEO: %s",
            corporation,
            corporation.ceo,
        )

        required_scopes = ["esi-corporations.read_structures.v1"]

        token = Token.get_token(corporation.ceo.character_id, required_scopes)
        if token:
            logger.debug("Fetching structures for corporation %s", corporation)
            response = esi.client.Corporation.get_corporations_corporation_id_structures(
                corporation_id=corporation.corporation_id,
                token=token.valid_access_token(),
            ).results()

            known_structure_ids = []
            for structure in response:
                logger.info("Updating structure %s", structure["name"])
                logger.debug("Structure details %s", structure)
                system, _ = EveSolarSystem.objects.get_or_create_esi(
                    id=structure["system_id"]
                )
                structure_type, _ = EveType.objects.get_or_create_esi(
                    id=structure["type_id"]
                )
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
                    eve_structure.state_timer_start = structure[
                        "state_timer_start"
                    ]
                    eve_structure.state_timer_end = structure[
                        "state_timer_end"
                    ]
                    eve_structure.fuel_expires = structure["fuel_expires"]
                    eve_structure.save()
                else:
                    logger.debug(
                        "Creating new structure %s", structure["name"]
                    )
                    eve_structure = EveStructure.objects.create(
                        id=structure["structure_id"],
                        system_id=structure["system_id"],
                        system_name=system.name,
                        type_id=structure["type_id"],
                        type_name=structure_type.name,
                        name=structure["name"],
                        reinforce_hour=structure["reinforce_hour"],
                        state=structure["state"],
                        state_timer_start=structure["state_timer_start"],
                        state_timer_end=structure["state_timer_end"],
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
            logger.warning("No CEO token with structure access scope")
    else:
        logger.info(
            "Corporation %s does not have valid CEO token",
            corporation,
        )


@app.task
def process_structure_notifications(
    current_minute: datetime | None = None,
):
    if current_minute is None:
        current_minute = timezone.now().minute

    total_found = 0

    for esm in structure_managers_for_minute(current_minute):
        logger.info(
            "Fetching notifications for %s in %s",
            esm.character.character_name,
            esm.corporation.name,
        )
        total_found += fetch_structure_notifications(esm)

    if total_found > 0:
        logger.info("Found a total of %d structure notifications", total_found)

    return total_found


def fetch_structure_notifications(manager: EveStructureManager):
    response = EsiClient(manager.character).get_character_notifications()
    if not response.success():
        logger.error(
            "Error %d fetching notifications for %s",
            response.response_code,
            manager.character.character_name,
        )
        return 0

    manager.last_polled = timezone.now()
    manager.save()

    combat_types = [
        "StructureDestroyed",
        "StructureLostArmor",
        "StructureLostShields",
        "StructureUnderAttack",
    ]

    total_found = 0
    for notification in response.results():
        if notification["type"] in combat_types:
            data = parse_structure_notification(notification["text"])
            _, created = EveStructurePing.objects.get_or_create(
                notification_id=notification["notification_id"],
                defaults={
                    "notification_type": notification["type"],
                    "summary": data["text"],
                    "structure_id": data["structure_id"],
                },
            )
            logger.info(
                "Found notification %d %s %s : %s, created=%s",
                notification["notification_id"],
                notification["timestamp"],
                notification["type"],
                data["text"],
                created,
            )

            total_found += 1

    return total_found


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

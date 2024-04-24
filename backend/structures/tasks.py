import logging

from esi.clients import EsiClientProvider
from esi.models import Token
from eveuniverse.models import EveSolarSystem, EveType

from app.celery import app
from eveonline.models import EveCorporation

from .models import EveStructure

esi = EsiClientProvider()
logger = logging.getLogger(__name__)


@app.task
def update_structures():
    for corporation in EveCorporation.objects.all():
        logger.info("Checking corporation %s for structures", corporation)
        if corporation.ceo and corporation.ceo.token:
            required_scopes = ["esi-corporations.read_structures.v1"]
            if Token.objects.filter(
                character_id=corporation.ceo.character_id,
                scopes__name__in=required_scopes,
            ).exists():
                token = Token.objects.filter(
                    character_id=corporation.ceo.character_id,
                    scopes__name__in=required_scopes,
                ).first()
                logger.info(
                    "Fetching structures for corporation %s", corporation
                )
                response = esi.client.Corporation.get_corporations_corporation_id_structures(
                    corporation_id=corporation.corporation_id,
                    token=token.valid_access_token(),
                ).results()

                known_structure_ids = []
                for structure in response:
                    logger.info("Processing structure %s", structure)
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
                        logger.info(
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
                        logger.info(
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
                structures = EveStructure.objects.filter(
                    corporation=corporation
                )
                for structure in structures:
                    if structure.id not in known_structure_ids:
                        logger.info("Deleting structure %s", structure.name)
                        structure.delete()
        else:
            logger.info(
                "Corporation %s does not have CEO token",
                corporation,
            )

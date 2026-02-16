import logging

from app.celery import app
from eveonline.client import EsiClient
from eveonline.helpers.characters import update_character_with_affiliations
from eveonline.models import EveCharacter
from groups.tasks import update_affiliation

logger = logging.getLogger(__name__)

task_config = {
    "async_apply_affiliations": True,
}


@app.task
def update_character_affilliations() -> int:
    character_ids = EveCharacter.objects.values_list("character_id", flat=True)
    logger.info(
        "Update character affiliations, %d characters found",
        len(character_ids),
    )

    character_id_batches = []
    # batch in groups of 1000
    for i in range(0, len(character_ids), 1000):
        character_id_batches.append(character_ids[i : i + 1000])

    update_count = 0

    for character_ids_batch in character_id_batches:
        results = (
            EsiClient(None)
            .get_character_affiliations(character_ids_batch)
            .results()
        )
        logger.info(
            "Update character affiliations, processing %d characters, %d results",
            len(character_ids_batch),
            len(results),
        )
        for result in results:
            character_id = result["character_id"]
            corporation_id = result.get("corporation_id")
            alliance_id = result.get("alliance_id")
            faction_id = result.get("faction_id")

            character = EveCharacter.objects.get(character_id=character_id)

            updated = update_character_with_affiliations(
                character_id=character_id,
                corporation_id=corporation_id,
                alliance_id=alliance_id,
                faction_id=faction_id,
            )

            if updated:
                logger.info(
                    "Update character affiliations, character updated: %s (%s)",
                    character_id,
                    character.user_id,
                )
                update_count += 1
                if character.user:
                    if task_config["async_apply_affiliations"]:
                        update_affiliation.apply_async(
                            args=[character.user.id]
                        )
                    else:
                        update_affiliation(character.user.id)

    logger.info(
        "Update character affiliations complete with %d changes",
        update_count,
    )
    return update_count

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


@app.task(expires=15 * 60, exclusive=15 * 60)
def update_character_affilliations() -> int:
    character_ids = list(
        EveCharacter.objects.values_list("character_id", flat=True)
    )
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
        response = EsiClient(None).get_character_affiliations(
            character_ids_batch
        )
        if not response.success():
            logger.warning(
                "Skipping affiliations batch of %d characters, ESI error %s",
                len(character_ids_batch),
                response.response_code,
            )
            continue
        results = response.results()
        logger.info(
            "Update character affiliations, processing %d characters, %d results",
            len(character_ids_batch),
            len(results),
        )
        characters = {
            character.character_id: character
            for character in EveCharacter.objects.filter(
                character_id__in=[r["character_id"] for r in results]
            ).only("pk", "character_id", "user_id")
        }
        for result in results:
            character_id = result["character_id"]
            corporation_id = result.get("corporation_id")
            alliance_id = result.get("alliance_id")
            faction_id = result.get("faction_id")

            character = characters.get(character_id)
            if character is None:
                continue

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
                if character.user_id:
                    if task_config["async_apply_affiliations"]:
                        update_affiliation.apply_async(
                            args=[character.user_id]
                        )
                    else:
                        update_affiliation(character.user_id)

    logger.info(
        "Update character affiliations complete with %d changes",
        update_count,
    )
    return update_count

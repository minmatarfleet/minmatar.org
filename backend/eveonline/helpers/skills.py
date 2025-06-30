import json
import logging
from typing import List

import pydantic
from eveonline.client import EsiClient

from eveonline.models import (
    EveCharacter,
    EveCharacterSkill,
    EveCharacterSkillset,
    EveSkillset,
)

logger = logging.getLogger(__name__)


class EveCharacterSkillResponse(pydantic.BaseModel):
    skill_id: int
    skill_name: str
    skillpoints_in_skill: int
    trained_skill_level: int


def upsert_character_skills(character_id: int):
    """
    populate skills from eve and save them to the character

    """
    logger.debug("Upserting skills for character %s", character_id)
    character = EveCharacter.objects.get(character_id=character_id)

    response = EsiClient(character).get_character_skills()

    if not response.success():
        logger.error(
            "Error %s getting skills for %s",
            response.error_text(),
            character.summary(),
        )
        return

    for skill in response.results():
        upsert_character_skill(character, skill)


def upsert_character_skill(character: EveCharacter, esi_skill):
    skill_type = EsiClient(None).get_eve_type(esi_skill["skill_id"])

    qry = EveCharacterSkill.objects.filter(
        character=character, skill_id=esi_skill["skill_id"]
    ).order_by("-skill_points")

    logger.debug("Query count %d", qry.count())

    if qry.count() == 0:
        skill = EveCharacterSkill(
            character=character,
            skill_id=esi_skill["skill_id"],
            skill_name=skill_type.name,
            skill_points=esi_skill["skillpoints_in_skill"],
            skill_level=esi_skill["trained_skill_level"],
        )
    else:
        skill = qry.first()
        skill.skill_points = esi_skill["skillpoints_in_skill"]
        skill.skill_level = esi_skill["trained_skill_level"]

    skill.save()

    if qry.count() > 1:
        logger.error(
            "Duplicate skill %d for character %d, deleting one",
            esi_skill["skill_id"],
            character.character_id,
        )
        # If more than 2, eventually all but 1 will be removed
        qry.last().delete()


def compare_skills_to_skillset(character_id: int, skillset: EveSkillset):
    """Compare a character's skills to a skillset"""
    character = EveCharacter.objects.get(character_id=character_id)
    character_skills = EveCharacterSkill.objects.filter(character=character)
    skills: List[EveCharacterSkillResponse] = []
    for skill in character_skills:
        skills.append(
            EveCharacterSkillResponse(
                skill_id=skill.skill_id,
                skill_name=skill.skill_name,
                skillpoints_in_skill=skill.skill_points,
                trained_skill_level=skill.skill_level,
            )
        )

    # create a lookup hashmap from skillset
    skillset_lookup = {}
    for skill in skillset.skills.split("\n"):
        skill = skill.strip()
        skillset_lookup[skill] = True

    # populate skills from eve universe data
    hydrated_skills = {}
    for skill in skills:
        hydrated_skills[skill.skill_name] = skill.model_dump()

    # build progress of skillset
    missing_skills = []
    player_skill_count = 0
    total_skill_count = 0
    for skill in skillset_lookup:
        logger.debug("Checking skill %s", skill)
        # skill level is the last digit in string, remove it
        skill_name = skill[:-1].strip()
        skill_level = int(skill[-1])

        if skill_name not in hydrated_skills:
            missing_skills.append(skill)
            total_skill_count += skill_level * 12
        else:
            logger.debug(
                "Player has skill %s at level %s",
                skill_name,
                hydrated_skills[skill_name]["trained_skill_level"],
            )
            if (
                hydrated_skills[skill_name]["trained_skill_level"]
                < skill_level
            ):
                missing_skills.append(skill)
                total_skill_count += skill_level * 12
            player_skill_count += skill_level * 12

    if missing_skills:
        progress = player_skill_count / total_skill_count
    else:
        progress = 100
    return missing_skills, int(progress)


def create_eve_character_skillset(character_id: int, skillset: EveSkillset):
    """Create a skillset for a character"""
    # delete existing
    logger.debug(
        "Creating skillset for character %s and skillset %s",
        character_id,
        skillset.name,
    )
    character = EveCharacter.objects.get(character_id=character_id)
    EveCharacterSkillset.objects.filter(
        character=character, eve_skillset=skillset
    ).delete()
    missing_skills, progress = compare_skills_to_skillset(
        character_id, skillset
    )
    logger.debug(
        "Character %s has %s missing skills for skillset %s",
        character.character_id,
        len(missing_skills),
        skillset.name,
    )
    return EveCharacterSkillset.objects.create(
        character=character,
        eve_skillset=skillset,
        progress=progress,
        missing_skills=json.dumps(missing_skills),
    )

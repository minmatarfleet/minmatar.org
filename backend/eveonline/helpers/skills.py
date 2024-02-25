import json
import logging
from typing import List

import pydantic
from eveuniverse.models import EveType

from eveonline.models import EveCharacter, EveCharacterSkillset, EveSkillset

logger = logging.getLogger(__name__)


class EveCharacterSkillResponse(pydantic.BaseModel):
    skill_id: int
    skillpoints_in_skill: int
    trained_skill_level: int


def compare_skills_to_skillset(character: EveCharacter, skillset: EveSkillset):
    """Compare a character's skills to a skillset"""
    skills: List[EveCharacterSkillResponse] = json.loads(
        character.skills_json
    )["skills"]

    # create a lookup hashmap from skillset
    skillset_lookup = {}
    for skill in skillset.skills.split("\n"):
        skill = skill.strip()
        skillset_lookup[skill] = True

    # populate skills from eve universe data
    hydrated_skills = {}
    for skill in skills:
        esi_skill, _ = EveType.objects.get_or_create_esi(id=skill["skill_id"])
        skill_name = esi_skill.name
        hydrated_skills[skill_name] = skill

    # build progress of skillset
    missing_skills = []
    player_skill_count = 0
    total_skill_count = 0
    for skill in skillset_lookup:
        logger.info("Checking skill %s", skill)
        # skill level is the last digit in string, remove it
        skill_name = skill[:-1].strip()
        skill_level = int(skill[-1])

        if skill_name not in hydrated_skills:
            missing_skills.append(skill)
            total_skill_count += skill_level * 12
        else:
            logger.info(
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


def create_eve_character_skillset(
    character: EveCharacter, skillset: EveSkillset
):
    """Create a skillset for a character"""
    # delete existing
    logger.info(
        "Creating skillset for character %s and skillset %s",
        character.character_id,
        skillset.name,
    )
    EveCharacterSkillset.objects.filter(
        character=character, eve_skillset=skillset
    ).delete()
    missing_skills, progress = compare_skills_to_skillset(character, skillset)
    logger.info(
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

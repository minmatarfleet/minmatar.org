import pydantic
from typing import List
from eveuniverse.models import EveType
from eveonline.models import EveCharacterSkillset, EveCharacter
import json


class EveCharacterSkillResponse(pydantic.BaseModel):
    skill_id: int
    skillpoints_in_skill: int
    trained_skill_level: int


def compare_skills_to_skillset(
    character: EveCharacter, skillset: EveCharacterSkillset
):
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
        # skill level is the last digit in string, remove it
        skill_name = skill[:-1].strip()
        skill_level = int(skill[-1])

        if skill_name not in hydrated_skills:
            missing_skills.append(skill)
            total_skill_count += skill_level * 12
        else:
            player_skill_count += skill_level * 12

    if missing_skills:
        progress = player_skill_count / total_skill_count
    else:
        progress = 100
    return missing_skills, int(progress)

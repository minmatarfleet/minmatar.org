import type { CharacterSkillset, Character } from '@dtypes/api.minmatar.org'
import type { SkillsetsUI, Skillset, MissingSkill } from '@dtypes/layout_components'
import { get_character_by_id, get_character_skillsets } from '@helpers/api.minmatar.org/characters'

export async function get_skillsets(access_token:string, character_id: number) {
    let skillsets:Skillset[]
    let character_skillsets:CharacterSkillset[]
    let character:Character

    character = await get_character_by_id(access_token, character_id)

    character_skillsets = await get_character_skillsets(access_token, character_id)
    skillsets = character_skillsets.map( (i):Skillset => {
        return {
            name: i.name,
            progress: i.progress,
            missing_skills: i.missing_skills.map( (skillname) => parse_missing_skill(skillname) )
        }
    })

    return {
        character_id: character.character_id,
        character_name: character.character_name,
        skillsets: skillsets
    } as SkillsetsUI
}

const parse_missing_skill = (skill_name):MissingSkill => {
    let list = skill_name.split(" ")

    return {
        skill_level: list.pop(),
        skill_name: list.join(" ")
    }
}
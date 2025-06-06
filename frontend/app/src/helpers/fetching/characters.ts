import { useTranslations } from '@i18n/utils';

import type { CharacterSkillset, Character, CharacterAsset, UserProfile, EveCharacterProfile, SummaryCharacter } from '@dtypes/api.minmatar.org'
import type { CharacterTagSummary, CharacterErrorUI } from '@dtypes/layout_components'
import type {
    SkillsetsUI,
    Skillset,
    MissingSkill,
    AssetsUI,
    AssetsLocation,
    Asset,
    AssetsLocationIcons,
    AssetGroup,
} from '@dtypes/layout_components'
import {
    get_character_by_id,
    get_character_skillsets,
    get_character_assets,
    get_characters,
    get_characters_summary,
    get_character_tags,
} from '@helpers/api.minmatar.org/characters'
import { get_user_by_id, get_users_by_id } from '@helpers/api.minmatar.org/authentication'

export async function get_user_character(user_id:number, lang:'en' = 'en') {
    const t = useTranslations(lang);

    let user_profile:UserProfile | null = null
    try {
        user_profile = await get_user_by_id(user_id)
    } catch (error) {
        return {
            character_id: 0,
            character_name: t('unknown_pilot'),
            corporation_id: 0,
            corporation_name: t('unknown_corporation'),
            user_id: user_id,
            scopes: [],
        } as EveCharacterProfile
    }

    const character_profile = user_profile.eve_character_profile
    
    if (character_profile)
        character_profile.user_id = user_id

    return character_profile
}

export async function get_users_character(user_id:number[]) {
    const users_profile = await get_users_by_id(user_id)
    return users_profile.map(profile => {
        const character_profile = profile.eve_character_profile

        if (character_profile)
            character_profile.user_id = profile.user_id

        return character_profile
    }) as EveCharacterProfile[]
}

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

export async function get_assets(access_token:string, character_id: number) {
    const assets_locations_names:string[] = []
    let assets_locations_icons:AssetsLocationIcons[] = []
    let assets_locations:AssetsLocation[] = []
    let character:Character
    let assets:CharacterAsset[]

    character = await get_character_by_id(access_token, character_id)

    assets = await get_character_assets(access_token, character_id)

    assets.forEach( (i) => {
        if (!assets_locations_names.includes(i.location_name))
            assets_locations_names.push(i.location_name)
    })

    assets_locations_icons = assets_locations_names.map( (location_name):AssetsLocationIcons => {
        return {
            location_name: location_name,
            assets: assets.filter( (asset) => asset.location_name === location_name )
                    .map( (i):Asset => {
                        return {
                            id: i.type_id,
                            name: i.type_name,
                        }
                    })
        }
    })

    assets_locations = assets_locations_icons.map( (assets_location):AssetsLocation => {
        const location_types_id:number[] = []

        assets_location.assets.forEach( (i) => {
            if (!location_types_id.includes(i.id))
                location_types_id.push(i.id)
        })

        return {
            location_name: assets_location.location_name,
            assets: location_types_id.map( (type_id):AssetGroup => {
                const filtered_assets = assets_location.assets.filter( (asset) => asset.id == type_id )

                return {
                    id: filtered_assets[0].id,
                    name: filtered_assets[0].name,
                    count: filtered_assets.length,
                }
            })
        }
    })

    return {
        character_id: character.character_id,
        character_name: character.character_name,
        locations: assets_locations,
        location_icons: assets_locations_icons,
    } as AssetsUI
}

const parse_missing_skill = (skill_name):MissingSkill => {
    let list = skill_name.split(" ")

    return {
        skill_level: list.pop(),
        skill_name: list.join(" ")
    }
}

export async function get_user_assets(access_token:string) {
    let characters:Character[]
    let characters_assets:AssetsUI[]

    characters = await get_characters(access_token)
    
    characters_assets = await Promise.all(characters.map(async (character) => {
        let character_assets:AssetsUI = {
            character_id: character.character_id,
            character_name: character.character_name,
            locations: [],
            location_icons: [],
        }

        try {
            character_assets = await get_assets(access_token, character.character_id)
        } catch (error) {
            throw new Error(error);
        }

        return character_assets
    }))

    return characters_assets
}

export async function esi_token_error(auth_token: string) {
    try {
        const character_summary = await get_characters_summary(auth_token)
        
        return character_summary.characters.find(character => character.token_status !== 'ACTIVE') !== undefined
    } catch (error) {
        return false
    }
}

export async function  get_tags_summary(auth_token: string) {
    const character_summary = await get_characters_summary_sorted(auth_token)
    
    return await Promise.all(character_summary.characters.map(async character => {
        const character_tags = (await get_character_tags(auth_token, character.character_id)).map(character_tag => character_tag.id)
        
        return {
            character_id: character.character_id,
            character_name: character.character_name,
            tags: character_tags,
        } as CharacterTagSummary
    }))
}

export async function get_characters_summary_sorted(auth_token: string) {
    const character_summary = await get_characters_summary(auth_token)
    character_summary.characters = character_summary.characters.sort((a, b) => (Number)(b.is_primary === true) - (Number)(a.is_primary === true) || a.character_name.localeCompare(b.character_name))
    return character_summary
}

export function get_character_error_ui(characters:SummaryCharacter[]) {
    let character_errors:CharacterErrorUI[] = []
    let no_main = true

    characters.forEach(character => {
        no_main = character.is_primary ? false : no_main

        if (character.flags.length > 0) {
            character.flags.forEach(flag => {
                character_errors.push({
                    character: character,
                    error: flag,
                })
            })
        }
    })

    if (no_main) character_errors.push({
        error: 'NO_MAIN_SET',
    })

    return character_errors
}
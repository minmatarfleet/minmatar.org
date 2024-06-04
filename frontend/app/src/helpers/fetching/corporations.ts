import { useTranslations } from '@i18n/utils';
import { get_user_character } from '@helpers/fetching/characters'
import type { EveCharacterProfile } from '@dtypes/api.minmatar.org'

const t = useTranslations('en');

import type { Corporation, CorporationApplication, CorporationType, CharacterCorp } from '@dtypes/api.minmatar.org'
import type { CorporationObject, CorporationStatusType, CorporationMembers, CharacterKind, CharacterBasic } from '@dtypes/layout_components'
import { get_all_corporations, get_corporation_by_id } from '@helpers/api.minmatar.org/corporations'
import { get_corporation_applications } from '@helpers/api.minmatar.org/applications'

export async function get_corporations_list_auth(access_token:string, user_id: number, corporation_type:CorporationType) {
    let api_corporations:Corporation[] = []
    let corporations:CorporationObject[] = []

    api_corporations = await get_all_corporations(corporation_type)

    corporations = await Promise.all(api_corporations.map(async (i) => add_status_to_corporation(access_token, i, user_id) ));
    
    return corporations
}

export async function get_corporations_list(corporation_type:CorporationType) {
    let api_corporations:Corporation[] = []
    let corporations:CorporationObject[] = []

    api_corporations = await get_all_corporations(corporation_type)

    corporations = api_corporations.map( (i):CorporationObject => {
        return {
            alliance_id: i.alliance_id,
            alliance_name: i.alliance_name,
            corporation_id: i.corporation_id,
            corporation_name: i.corporation_name,
            corporation_type: i.type,
            active: i.active,
            biography: i.biography,
            introduction: i.introduction,
            requirements: i.requirements,
            timezones: i.timezones,
            status: 'unauth'
        }
    } )
    
    return corporations
}

export async function get_corporation_list_by_id_auth(access_token:string, corporation_id:number, user_id: number) {
    let api_corporation:Corporation

    api_corporation = await get_corporation_by_id(access_token, corporation_id)

    return await add_status_to_corporation(access_token, api_corporation, user_id)
}

const add_status_to_corporation = async (access_token:string, api_corporation:Corporation, user_id:number) => {
    let corporation_applications:CorporationApplication[]

    const corporation:CorporationObject = {
        corporation_id: api_corporation.corporation_id,
        corporation_name: api_corporation.corporation_name,
        alliance_id: api_corporation.alliance_id,
        alliance_name: api_corporation.alliance_name,
        corporation_type: api_corporation.type,
        active: api_corporation.active,
        status: 'available',
        biography: api_corporation.biography,
        introduction: api_corporation.introduction,
        requirements: api_corporation.requirements,
        timezones: api_corporation.timezones,
    }

    try {
        corporation_applications = await get_corporation_applications(access_token, api_corporation.corporation_id)
    } catch (error) {
        corporation.status = 'error'
        return corporation
    }
    
    const user_application = user_id ? corporation_applications.find( (application) => application.user_id == user_id ) : undefined

    if (user_application !== undefined)
        corporation.status = user_application.status as CorporationStatusType

    return corporation
}

export async function get_user_corporation_id(user_id:number) {
    let user_character:EveCharacterProfile
    user_character = (user_id ? await get_user_character(user_id) : null)
    return !user_character ? null : (user_character?.corporation_id ?? null)
}

export async function get_all_corporations_members(access_token:string) {
    let api_corporations:Corporation[]
    let corporation_members:CorporationMembers[]

    api_corporations = await get_all_corporations('alliance')

    corporation_members = (await Promise.all(api_corporations.map(async (corporation) => 
        await get_all_corporation_members(access_token, corporation.corporation_id)
    )))

    return corporation_members
}

export async function get_all_corporation_members(access_token:string, corporation_id:number) {
    let api_corporation:Corporation
    let corporation_members:CorporationMembers

    api_corporation = await get_corporation_by_id(access_token, corporation_id)

    corporation_members = {
        corporation_id: api_corporation.corporation_id,
        corporation_name: api_corporation.corporation_name,
        active: api_corporation.active,
        type: api_corporation.type,
        members: []
    }

    corporation_members.members = (await Promise.all(api_corporation.members.map(async (api_member) => {
        const is_alt = (api_member.primary_character_id !== null)

        let member:CharacterKind = {
            character_id: api_member.character_id,
            character_name: api_member.character_name,
            registered: api_member.registered,
            exempt: api_member.exempt,
            is_main: !is_alt
        }
        
        if (is_alt) {
            member.main_character = {
                character_id: api_member.primary_character_id,
                character_name: api_member.primary_character_name,
            }
        }

        return member
    })))

    return corporation_members
}

export async function get_all_alliance_members(access_token:string) {
    let members:CharacterBasic[] = []    
    let api_corporations:Corporation[]
    let corporation_members:CorporationMembers[]

    api_corporations = await get_all_corporations('alliance')

    corporation_members = (await Promise.all(api_corporations.map(async (corporation) => 
        await get_all_corporation_members(access_token, corporation.corporation_id)
    )))

    corporation_members.map( (corporation) =>
        corporation.members.map( (member) => {
            members.push({
                character_id: member.character_id,
                character_name: member.character_name,
                corporation: {
                    id: corporation.corporation_id,
                    name: corporation.corporation_name,
                }
            })
        })
    )

    return members
}
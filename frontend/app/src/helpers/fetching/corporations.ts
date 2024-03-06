import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { Corporation, CorporationApplication, UserProfile, CorporationType } from '@dtypes/api.minmatar.org'
import type { CorporationObject, GroupStatus } from '@dtypes/layout_components'
import { get_all_corporations, get_corporation_by_id } from '@helpers/api.minmatar.org/corporations'
import { get_corporation_applications } from '@helpers/api.minmatar.org/applications'
import { get_user_by_id } from '@helpers/api.minmatar.org/authentication'

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
            corporation_type: i.corporation_type,
            status: 'unauth'
        }
    } )
    
    return corporations
}

export async function get_corporation_list_by_id_auth(access_token:string, corporation_id:number, user_id: number) {
    let api_corporation:Corporation
    let corporation:CorporationObject

    api_corporation = await get_corporation_by_id(corporation_id)

    corporation = await add_status_to_corporation(access_token, api_corporation, user_id)
    
    return corporation
}

export async function get_corporation_list_by_id(corporation_id:number) {
    let api_corporation:Corporation

    api_corporation = await get_corporation_by_id(corporation_id)
    
    return {
        alliance_id: api_corporation.alliance_id,
        alliance_name: api_corporation.alliance_name,
        corporation_id: api_corporation.corporation_id,
        corporation_name: api_corporation.corporation_name,
        corporation_type: api_corporation.corporation_type,
        status: 'unauth'
    } as CorporationObject
}

const add_status_to_corporation = async (access_token:string, api_corporation:Corporation, user_id:number) => {
    let corporation_applications:CorporationApplication[]

    const corporation:CorporationObject = {
        corporation_id: api_corporation.corporation_id,
        corporation_name: api_corporation.corporation_name,
        alliance_id: api_corporation.alliance_id,
        alliance_name: api_corporation.alliance_name,
        corporation_type: api_corporation.corporation_type,
        status: 'available'
    }

    try {
        corporation_applications = await get_corporation_applications(access_token, api_corporation.corporation_id)
    } catch (error) {
        corporation.status = 'error'
        return corporation
    }
    
    const user_application = user_id ? corporation_applications.filter( (application) => application.user_id == user_id ) : []

    if (user_application.length > 0)
        corporation.status = user_application[0].status as GroupStatus

    return corporation
}

export async function get_user_corporation_id(user_id: number) {
    let user_profile:UserProfile
    user_profile = await get_user_by_id(user_id)
    return user_profile.eve_character_profile.corporation_id
}
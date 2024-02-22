import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import { cacheFn } from '@helpers/cache'
import type { Group, GroupRequest, UserProfile } from '@dtypes/api.minmatar.org'
import type { GroupRequestUI, GroupRequestListUI } from '@dtypes/layout_components'
import { get_managed_groups, get_group_requests, get_group_by_id } from '@helpers/api.minmatar.org/groups'
import { get_user_by_id } from '@helpers/api.minmatar.org/authentication'

export async function get_all_groups_requests(access_token:string) {
    let groups:Group[] = []
    let requests:GroupRequestListUI[]

    groups = await get_managed_groups(access_token)

    requests = await Promise.all(groups.map(async (request) => get_group_request(access_token, request)));

    return requests
}

export async function get_group_requests_by_id(access_token:string, group_id:number) {
    let group:Group
    let request:GroupRequestListUI

    group = await get_group_by_id(access_token, group_id)

    request = await get_group_request(access_token, group)

    return request
}

export async function get_group_request_by_id(access_token:string, group_id:number, request_id:number) {
    let group:Group
    let api_request:GroupRequest
    let api_requests:GroupRequest[]
    let request:GroupRequestUI

    group = await get_group_by_id(access_token, group_id)

    api_requests = await get_group_requests(access_token, group_id)
    api_request = api_requests[0]

    request = await get_group_request_ui(access_token, group, api_request)

    return request
}

const get_group_request = async (access_token:string, group:Group) => {
    let api_requests:GroupRequest[]
    let requests:GroupRequestUI[]

    api_requests = await get_group_requests(access_token, group.id)
    api_requests = api_requests.filter( (i) => i.approved === null )

    requests = await Promise.all(api_requests.map(async (api_request) => get_group_request_ui(access_token, group, api_request) ?? null ));

    return {
        group_id: group.id,
        group_name: group.name,
        group_image: group.image_url,
        requests: requests
    }
}

const get_group_request_ui = async (access_token:string, group:Group, api_request:GroupRequest) => {
    let request:GroupRequestUI
    let user_profile:UserProfile
    
    try {
        user_profile = await cached_get_user_info(access_token, api_request.user)
    } catch (error) {
        user_profile = {
            user_id: api_request.user,
            username: t('unknown_user'),
            permissions: [],
            is_superuser: false,
            eve_character_profile: {
                character_id: 0,
                character_name: t('unknown_character'),
                corporation_id: 0,
                corporation_name: t('unknown_corporation'),
                scopes: [],
            },
            discord_user_profile: null,
        }
    }

    request = {
        request_id: api_request.id,
        approved: api_request.approved,
        group_id: group.id,
        group_name: group.name,
        character_id: user_profile.eve_character_profile.character_id,
        character_name: user_profile.eve_character_profile.character_name,
        corporation_id: user_profile.eve_character_profile.corporation_id,
        corporation_name: user_profile.eve_character_profile.corporation_name,
        group_image: group.image_url,
        description: group.description
    }

    return request
}

const get_user_info = async (access_token:string, user_id:number) => {
    let user_profile:UserProfile

    user_profile = await get_user_by_id(access_token, user_id)

    return user_profile
}

const cached_get_user_info = cacheFn(get_user_info)
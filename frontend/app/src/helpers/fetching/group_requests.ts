import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import { cachePromise } from '@helpers/cache'
import type { Group, SigRequest, TeamRequest, UserProfile } from '@dtypes/api.minmatar.org'
import type { GroupRequestUI, GroupRequestListUI, GroupItemType } from '@dtypes/layout_components'
import {
    get_groups as get_sigs,
    get_current_groups as get_current_sigs,
    get_group_requests as get_sigs_requests,
    get_group_by_id as get_sig_by_id
} from '@helpers/api.minmatar.org/sigs'
import {
    get_groups as get_teams,
    get_current_groups as get_current_teams,
    get_group_requests as get_teams_requests,
    get_group_by_id as get_team_by_id
} from '@helpers/api.minmatar.org/teams'
import { get_user_by_id } from '@helpers/api.minmatar.org/authentication'

export async function get_all_groups_requests(access_token:string, group_type:GroupItemType, superuser?:boolean) {
    let groups:Group[] = []
    let requests:GroupRequestListUI[]

    if(group_type === 'team')
        groups = superuser ? await get_teams() : await get_current_teams(access_token)
    else
        groups = superuser ? await get_sigs() : await get_current_sigs(access_token)

    requests = await Promise.all(groups.map(async (request) => get_group_request(access_token, request, group_type)));

    return requests
}

export async function get_group_requests_by_id(access_token:string, group_id:number, group_type:GroupItemType) {
    let group:Group
    let request:GroupRequestListUI

    if(group_type === 'team')
        group = await get_team_by_id(group_id)
    else
        group = await get_sig_by_id(group_id)

    request = await get_group_request(access_token, group, group_type)

    return request
}

export async function get_group_request_by_id(access_token:string, group_id:number, request_id:number, group_type:GroupItemType) {
    let group:Group
    let api_request:SigRequest | TeamRequest
    let api_requests:(SigRequest | TeamRequest)[]
    let request:GroupRequestUI

    if(group_type === 'team')
        group = await get_team_by_id(group_id)
    else
        group = await get_sig_by_id(group_id)


    if(group_type === 'team')
        api_requests = await get_teams_requests(access_token, group_id)
    else
        api_requests = await get_sigs_requests(access_token, group_id)

    api_request = api_requests[0]

    request = await get_group_request_ui(group, api_request, group_type)

    return request
}

const get_group_request = async (access_token:string, group:Group, group_type:GroupItemType) => {
    let api_requests:(SigRequest | TeamRequest)[]
    let requests:GroupRequestUI[]

    if(group_type === 'team')
        api_requests = await get_teams_requests(access_token, group.id)
    else
        api_requests = await get_sigs_requests(access_token, group.id)

    api_requests = api_requests.filter( (i) => i.approved === null )

    requests = await Promise.all(api_requests.map(async (api_request) => get_group_request_ui(group, api_request, group_type) ?? null ));

    return {
        group_id: group.id,
        group_name: group.name,
        group_image: group.image_url,
        requests: requests
    }
}

const get_group_request_ui = async (group:Group, api_request:SigRequest | TeamRequest, group_type:GroupItemType) => {
    let request:GroupRequestUI
    let user_profile:UserProfile
    
    try {
        user_profile = await get_user_info(api_request.user)
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

const get_user_info = async (user_id:number) => {
    let user_profile:UserProfile

    user_profile = await get_user_by_id(user_id)

    return user_profile
}
import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import type { Group, SigRequest, TeamRequest, UserProfile, EveCharacterProfile } from '@dtypes/api.minmatar.org'
import type { GroupItemType, GroupItemUI, GroupMembersUI, MemberUI, CharacterBasic } from '@dtypes/layout_components'

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

import { get_user_character } from '@helpers/fetching/characters'

export async function get_groups_auth(access_token:string, user_id: number, group_type:GroupItemType) {
    let api_groups:Group[]
    let groups:GroupItemUI[]

    api_groups = (group_type === 'team' ? await get_teams() : await get_sigs())

    groups = await Promise.all(api_groups.map(async (i) => add_status_to_group(access_token, i, user_id, group_type) ));

    return groups
}

export async function get_groups(group_type:GroupItemType) {
    let api_groups:Group[]
    let groups:GroupItemUI[]

    api_groups = (group_type === 'team' ? await get_teams() : await get_sigs())

    groups = api_groups.map( (api_group):GroupItemUI => {
        return {
            id: api_group.id,
            name: api_group.name,
            description: api_group.description,
            image_url: api_group.image_url,
            status: 'unauth'
        }
    } )

    return groups
}

export async function get_group_by_id_auth(access_token:string, group_id:number, user_id: number, group_type:GroupItemType) {
    let api_group:Group

    if (group_type == 'team')
        api_group = await get_team_by_id(group_id)
    else
        api_group = await get_sig_by_id(group_id)

    return await add_status_to_group(access_token, api_group, user_id, group_type)
}

export async function get_group_by_id(group_id:number, group_type:GroupItemType) {
    let api_group:Group

    if (group_type == 'team')
        api_group = await get_team_by_id(group_id)
    else
        api_group = await get_sig_by_id(group_id)
    
    return {
        id: api_group.id,
        name: api_group.name,
        description: api_group.description,
        image_url: api_group.image_url,
        status: 'unauth'
    } as GroupItemUI
}

const add_status_to_group = async (
    access_token:string,
    api_group:Group,
    user_id:number,
    group_type:GroupItemType
) => {
    let group_requests:SigRequest[] | TeamRequest[]

    const group:GroupItemUI = {
        id: api_group.id,
        name: api_group.name,
        description: api_group.description,
        image_url: api_group.image_url,
        status: 'available',
    }

    try {
        group_requests = (group_type === 'team' ? await get_teams_requests(access_token, api_group.id) : await get_sigs_requests(access_token, api_group.id))
    } catch (error) {
        group.status = 'error'
        return group
    }
    
    const user_request = user_id ? group_requests.findLast( (request) => request.user == user_id ) : undefined

    if (user_request !== undefined) {
        if (user_request.approved === null)
            group.status = 'requested'
        else if (user_request.approved === false)
            group.status = 'denied'

        group.last_update = user_request.approved_at
    }

    if (api_group.members.includes(user_id))
        group.status = 'confirmed'

    return group
}

export async function get_all_groups_members(access_token:string, group_type:GroupItemType, user_id:number, superadmin?:boolean) {
    let groups:Group[]
    let groups_members:GroupMembersUI[]

    if(group_type === 'team')
        groups = superadmin ? await get_teams() : await get_owned_teams(user_id)
    else
        groups = superadmin ? await get_sigs() : await get_owned_sigs(user_id)

    groups_members = await Promise.all(groups.map(async (group) => {
        let members:MemberUI[]

        members = await Promise.all(group.members.map(async (member_id) => {
            return await get_member(member_id)
        }))

        return {
            id: group.id,
            name: group.name,
            description: group.description,
            image_url: group.image_url,
            officers: group?.officers ?? group.directors,
            members: members,
        } as GroupMembersUI
    }));

    return groups_members
}

const get_member = async (user_id:number) => {
    let character_profile:EveCharacterProfile | null = null
    
    try {
        character_profile = await get_user_character(user_id)
    } catch (error) {
        character_profile = {
            character_id: 0,
            character_name: t('unknown_character'),
            corporation_id: 0,
            corporation_name: t('unknown_corporation'),
            scopes: [],
            user_id: user_id,
        }
    }

    return {
        user_id: user_id,
        character_id: character_profile?.character_id ?? 0,
        character_name: character_profile?.character_name ?? t('unknown_character'),
        corporation_id: character_profile?.corporation_id ?? 0,
        corporation_name: character_profile?.corporation_name ?? t('unknown_corporation'),
    } as MemberUI
}

export async function is_director(access_token:string, user_id:number) {
    let groups:Group[]
    
    try {
        groups = await get_current_teams(access_token)
    } catch (error) {
        return undefined
    }
    
    return groups.find( (group) => group.directors?.includes(user_id) ) !== undefined
}

export async function is_officer(access_token:string, user_id:number) {
    let groups:Group[]
    
    try {
        groups = await get_current_sigs(access_token)
    } catch (error) {
        return undefined
    }
    
    return groups.find( (group) => group?.officers?.includes(user_id) ) !== undefined
}

export async function get_all_members(access_token:string, user_id:number, superadmin?:boolean) {
    let groups_members:GroupMembersUI[] = []
    let team_members:GroupMembersUI[] = []
    let character_ids:number[] = []
    let members:CharacterBasic[] = []
    
    const user_is_officer = await is_officer(access_token, user_id)
    const user_is_director = await is_director(access_token, user_id)

    if (user_is_officer)
        groups_members = await get_all_groups_members(access_token, 'group', user_id, superadmin)
    
    if (user_is_director)
        team_members = await get_all_groups_members(access_token, 'team', user_id, superadmin)

    groups_members.forEach( (group) => {
        group.members.forEach( (member) => {
            if (character_ids.includes(member.character_id))
                return true

            character_ids.push(member.character_id)

            members.push({
                character_id: member.character_id,
                character_name: member.character_name,
                corporation: {
                    id: member.corporation_id,
                    name: member.corporation_name
                }
            })
        })
    })

    team_members.forEach( (group) => {
        group.members.forEach( (member) => {
            if (character_ids.includes(member.character_id))
                return true

            character_ids.push(member.character_id)

            members.push({
                character_id: member.character_id,
                character_name: member.character_name,
                corporation: {
                    id: member.corporation_id,
                    name: member.corporation_name
                }
            })
        })
    })

    return members
}

export async function get_owned_teams(user_id:number) {
    const groups = await get_teams()

    return groups.filter( (group) => group?.directors?.includes(user_id) )
}

export async function get_owned_sigs(user_id:number) {
    const groups = await get_sigs()

    return groups.filter( (group) => group?.officers?.includes(user_id) )
}
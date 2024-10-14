import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { FleetUI, FleetItem, DoctrineType, FleetCompositionUI, FleetRadarUI, CharacterBasic } from '@dtypes/layout_components'
import type { EveCharacterProfile, Fleet, FleetMember, FleetBasic, FleetUsers } from '@dtypes/api.minmatar.org'
import { get_fleets, get_fleets_v2, get_fleet_by_id, get_fleet_members } from '@helpers/api.minmatar.org/fleets'
import { get_route } from '@helpers/api.eveonline/routes'
import { get_user_character } from '@helpers/fetching/characters'
import { fetch_doctrine_by_id } from '@helpers/fetching/doctrines'
import { get_system_sun_type_id } from '@helpers/sde/map'
import { get_fleet_users } from '@helpers/api.minmatar.org/fleets'

const SOSALA_SYSTEM_ID = 30003070
const DEFAULT_STAGGERING_SYSTEM = SOSALA_SYSTEM_ID

export async function fetch_fleets_auth(access_token:string, upcoming:boolean = true) {
    let api_fleets_id:number[]

    api_fleets_id = await get_fleets(upcoming)

    return await Promise.all(api_fleets_id.map(async (fleet_id) => await add_fleet_info(access_token, fleet_id) ))
}

export async function fetch_fleets(upcoming:boolean = true) {
    let api_fleets_id:FleetBasic[]

    api_fleets_id = await get_fleets_v2(upcoming)

    return api_fleets_id.map((api_fleet) => {
        return {
            id: api_fleet.id,
            audience: api_fleet.audience,
            fleet_commander_id: 0,
            fleet_commander_name: t('not_available'),
            start_time: new Date('2100-01-01'),
        } as FleetItem
    } )
}

export async function add_fleet_info(access_token:string, fleet_id:number) {
    let fleet:Fleet 

    try {
        fleet = await get_fleet_by_id(access_token, fleet_id)
    } catch (error) {
        fleet = {
            id: fleet_id,
            doctrine_id: 0,
            location: '',
            type: 'non_strategic',
            description: '',
            start_time: new Date('2100-01-01'),
        } as Fleet
    }
        
    let character_profile:EveCharacterProfile | null = null
    if (fleet?.fleet_commander)
        character_profile = await get_user_character(fleet.fleet_commander)

    return {
        id: fleet.id,
        description: fleet.description,
        audience: fleet.audience,
        doctrine_id: fleet.doctrine_id,
        fleet_commander_id: character_profile?.character_id ?? 0,
        fleet_commander_name: character_profile?.character_name ?? t('not_available'),
        location: fleet.location,
        start_time: fleet.start_time,
        type: fleet.type,
        tracking: fleet.tracking,
    } as FleetItem
}

export async function fetch_fleet_by_id(access_token:string, fleet_id:number) {
    const fleet = await get_fleet_by_id(access_token, fleet_id)
        
    let character_profile:EveCharacterProfile | null = null
    if (fleet?.fleet_commander)
        character_profile = await get_user_character(fleet.fleet_commander)

    let doctrine:DoctrineType | null = null
    if (fleet?.doctrine_id)
        doctrine = await fetch_doctrine_by_id(fleet.doctrine_id)

    return {
        id: fleet.id,
        description: fleet.description,
        fleet_commander_id: character_profile?.character_id ?? 0,
        fleet_commander_name: character_profile?.character_name ?? t('unknown_character'),
        location: fleet.location,
        start_time: fleet.start_time,
        type: fleet.type,
        doctrine: fleet?.doctrine_id ? doctrine : null,
        tracking: fleet.tracking,
        audience: fleet.audience,
        disable_motd: fleet.disable_motd,
    } as FleetUI
}

export function group_members_by_ship(members:FleetMember[]):FleetCompositionUI[] {
    const ship_type_ids = [...new Set(members.map(member => member.ship_type_id))];

    return ship_type_ids.map((ship_type_id) => {
        const filtered_members = members.filter((member) => member.ship_type_id === ship_type_id)

        return {
            ship_type_id: ship_type_id,
            ship_type_name: filtered_members[0].ship_type_name,
            members: filtered_members.map((member):CharacterBasic => {
                return {
                    character_id: member.character_id,
                    character_name: member.character_name
                }
            })
        } as FleetCompositionUI
    })
}

export async function group_members_by_location(members:FleetMember[], staggering_solar_system_id:number = DEFAULT_STAGGERING_SYSTEM) {
    const solar_system_ids = [...new Set(members.map(member => member.solar_system_id))];

    return await Promise.all(solar_system_ids.map(async (solar_system_id) => {
        const filtered_members = members.filter((member) => member.solar_system_id === solar_system_id)
        const route = await get_route(solar_system_id, staggering_solar_system_id)

        return {
            solar_system_id: solar_system_id,
            solar_system_name: filtered_members[0].solar_system_name,
            start_type_id: await get_system_sun_type_id(solar_system_id),
            jumps: route.length - 1,
            members: filtered_members.map((member):CharacterBasic => {
                return {
                    character_id: member.character_id,
                    character_name: member.character_name
                }
            })
        } as FleetRadarUI
    })) as FleetRadarUI[]
}

export async function fetch_fleet_users(fleet_id:number) {
    const fleet_users = await get_fleet_users(fleet_id)
        
    if (fleet_users?.length > 0) {
        return fleet_users.find(() => true)?.user_ids
    }

    return []
}
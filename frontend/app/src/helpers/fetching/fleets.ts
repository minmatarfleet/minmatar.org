import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type {
    FleetUI,
    FleetItem,
    DoctrineType,
    FleetCompositionUI,
    FleetRadarUI,
    CharacterBasic,
    Locales,
    FleetTrackingTexts,
    Tracking,
} from '@dtypes/layout_components'
import type { EveCharacterProfile, Fleet, FleetMember, FleetMetrics, FleetCommanderMetrics } from '@dtypes/api.minmatar.org'
import {
    get_fleets_v3,
    get_fleet_by_id,
    get_fleets_metrics,
    get_fleet_commander_metrics,
} from '@helpers/api.minmatar.org/fleets'
import { get_route } from '@helpers/api.eveonline/routes'
import { get_user_character } from '@helpers/fetching/characters'
import { fetch_doctrine_by_id } from '@helpers/fetching/doctrines'
import { get_campaign } from '@helpers/api.minmatar.org/campaigns'
import { get_system_sun_type_id } from '@helpers/sde/map'
import { get_fleet_users } from '@helpers/api.minmatar.org/fleets'
import { time_diff_text } from '@helpers/date'
import { settled_value } from '@helpers/settled'

const SOSALA_SYSTEM_ID = 30003070
const DEFAULT_STAGGERING_SYSTEM = SOSALA_SYSTEM_ID

export async function fetch_fleets_auth(
    access_token:string,
    upcoming:boolean = true,
    simplified:boolean = false,
    fc_metrics:FleetCommanderMetrics[] | null = null,
) {
    let api_fleets:Fleet[]

    api_fleets = await get_fleets_v3(access_token, upcoming ? 'active' : 'recent')
    api_fleets = api_fleets.filter(api_fleet => api_fleet.fleet_commander)
    if (!upcoming)
        api_fleets = api_fleets.filter(api_fleet => api_fleet?.tracking || new Date(api_fleet.start_time ?? 0) < new Date())
    
    const fleet_ids = api_fleets.map(api_fleet =>  api_fleet.id)

    if (!simplified) {
        const fleets_metrics = await get_fleets_metrics(access_token)
        const fleets_metrics_filtered = fleets_metrics.filter(metric => fleet_ids.includes(metric.fleet_id))
        const fleet_commander_metrics = fc_metrics ? fc_metrics : await get_fleet_commander_metrics(access_token)

        return api_fleets.map( fleet => add_fleet_info(
            fleet,
            fleets_metrics_filtered,
            fleet_commander_metrics,
        ))
    }

    return api_fleets.map( fleet => add_fleet_info(fleet, [], []))
}

/** The FC's primary character comes with the fleet (fleet_commander_character_id / _name). */
export function add_fleet_info(
    fleet:Fleet,
    fleets_metrics:FleetMetrics[],
    fleet_commander_metrics:FleetCommanderMetrics[],
) {
    const fc_character_id = fleet.fleet_commander_character_id ?? null

    return {
        id: fleet.id,
        description: fleet.description,
        objective: fleet.objective,
        audience: fleet.audience,
        doctrine_id: fleet.doctrine_id,
        members_count: fleets_metrics.find(metric => metric.fleet_id === fleet.id)?.members,
        fleet_commander_id: fc_character_id ?? 0,
        fleet_commander_name: fleet.fleet_commander_name ?? t('not_available'),
        fleet_commander_fleet_count: fc_character_id === null ? undefined : fleet_commander_metrics.find(metric => metric.primary_character_id === fc_character_id)?.fleet_count,
        corporation_id: fleets_metrics.find(metric => metric.fleet_id === fleet.id)?.corporation_id,
        corporation_name: fleets_metrics.find(metric => metric.fleet_id === fleet.id)?.corporation_name,
        location: fleet.location,
        // FleetItem and FleetUI (layout_components) still call this a Date; it is the API's ISO string.
        start_time: fleet.start_time as unknown as Date,
        type: fleet.type,
        tracking: fleet.tracking as unknown as FleetItem['tracking'],  // same: the view-model's Dates are ISO strings
        status: fleet.status,
        aar_link: fleet.aar_link ?? null,
    } as FleetItem
}

async function fetch_campaign_name(access_token:string, campaign_slug:string):Promise<string | null> {
    // The fleet payload only carries the slug. The readable name is a bonus:
    // a viewer without the campaigns feature gets a 403 and keeps the slug.
    try {
        return (await get_campaign(campaign_slug, access_token))?.name ?? null
    } catch (error) {
        console.log(`Skipping campaign name: ${error.message}`)
        return null
    }
}

export async function fetch_fleet_by_id(access_token:string, fleet_id:number) {
    const fleet = await get_fleet_by_id(access_token, fleet_id)

    // FC, doctrine and campaign only need the fleet, so fetch them together.
    const [profile_result, doctrine_result, campaign_name_result] = await Promise.allSettled([
        fleet?.fleet_commander ? get_user_character(fleet.fleet_commander) : null,
        fleet?.doctrine_id ? fetch_doctrine_by_id(fleet.doctrine_id) : null,
        fleet?.campaign_slug ? fetch_campaign_name(access_token, fleet.campaign_slug) : null,
    ])
    const character_profile:EveCharacterProfile | null = settled_value(profile_result)
    const doctrine:DoctrineType | null = settled_value(doctrine_result)
    const campaign_name:string | null = settled_value(campaign_name_result)

    return {
        id: fleet.id,
        description: fleet.description,
        objective: fleet.objective,
        fleet_commander_id: character_profile?.character_id ?? 0,
        fleet_commander_name: character_profile?.character_name ?? t('unknown_character'),
        location: fleet.location,
        // FleetItem and FleetUI (layout_components) still call this a Date; it is the API's ISO string.
        start_time: fleet.start_time as unknown as Date,
        type: fleet.type,
        doctrine: fleet?.doctrine_id ? doctrine : null,
        tracking: fleet.tracking as unknown as FleetItem['tracking'],  // same: the view-model's Dates are ISO strings
        audience: fleet.audience,
        disable_motd: fleet.disable_motd,
        hide_volunteers: fleet.hide_volunteers,
        status: fleet.status,
        aar_link: fleet.aar_link ?? '',
        roam_report_url: fleet.roam_report_url ?? '',
        campaign_id: fleet.campaign_id ?? null,
        campaign_slug: fleet.campaign_slug ?? null,
        campaign_name: campaign_name,
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

export async function group_members_by_location(members:FleetMember[], staging_solar_system_id:number = DEFAULT_STAGGERING_SYSTEM) {
    const solar_system_ids = [...new Set(members.map(member => member.solar_system_id))];

    return await Promise.all(solar_system_ids.map(async (solar_system_id) => {
        const filtered_members = members.filter((member) => member.solar_system_id === solar_system_id)
        const route = await get_route(solar_system_id, staging_solar_system_id)

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

export async function fetch_fleet_users(access_token:string, fleet_id:number) {
    const fleet_users = await get_fleet_users(access_token, fleet_id)
        
    if (fleet_users?.length > 0) {
        return fleet_users.find(() => true)?.user_ids
    }

    return []
}

export function get_fleet_tracking_texts(locale:Locales = 'en', fleet_tracking?:Tracking): FleetTrackingTexts | false {
    try {
        const t = useTranslations(locale)
        const date_format = import.meta.env.DATETIME_FORMAT_SHORT ?? '{"year":"numeric","month":"short","day":"numeric","hour":"numeric","hourCycle":"h23","minute":"2-digit"}'

        if (fleet_tracking?.end_time) {
            const fleet_start_eve_time = new Date(fleet_tracking.start_time)
            const fleet_end_eve_time = new Date(fleet_tracking.end_time)
            const fleet_start_eve_time_text = fleet_start_eve_time.toLocaleDateString(locale, JSON.parse(date_format))
            const fleet_end_eve_time_text = fleet_end_eve_time.toLocaleDateString(locale, JSON.parse(date_format))
            const fleet_tracking_hint = t('fleet_tracking_hint').replace('FLEET_START', fleet_start_eve_time_text).replace('FLEET_END', fleet_end_eve_time_text)
            const fleet_duration_text = time_diff_text(locale, fleet_tracking.start_time, fleet_tracking.end_time)

            return {
                fleet_end_eve_time_text: fleet_end_eve_time_text,
                fleet_duration_text: fleet_duration_text,
                fleet_tracking_hint: fleet_tracking_hint,
            } as FleetTrackingTexts
        }
    } catch (error) {
        console.log(error)
    }

    return false
}
import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { SRPUI, FleetSRPUI, KillmailAnalysis, SRPFrontendPrograms } from '@dtypes/layout_components'
import { get_all_corporations } from '@helpers/api.minmatar.org/corporations'
import type { SRP, SRPStatus } from '@dtypes/api.minmatar.org'
import { get_fleet_srp, resolve_killmail, get_srp_programs } from '@helpers/api.minmatar.org/srp'
import { unique_values, get_unique_by_key } from '@helpers/array'
import { get_ships_type } from '@helpers/sde/ships'

export async function fetch_srps(access_token:string, status:SRPStatus = 'pending') {
    let api_fleet_srps:SRP[]

    const api_corporations = await get_all_corporations('alliance')
    const CORP_NAMES = {}
    const ship_types = {}
    api_corporations.map(api_corporation => CORP_NAMES[api_corporation.corporation_id] = api_corporation.corporation_name)

    api_fleet_srps = await get_fleet_srp(access_token, { status: status})
    const fleet_ids = unique_values(api_fleet_srps.map(srp => srp.fleet_id))
    
    const ships_id = api_fleet_srps.flatMap(api_fleet_srp => api_fleet_srp.ship_type_id)
    const ship_class = await get_ships_type(ships_id)
    ship_class.map(i => {
        ship_types[i.ship_id] = i.type
    })

    const fleets_srps = fleet_ids.map(fleet_id => {
        const srps = api_fleet_srps.filter(srp => srp.fleet_id === fleet_id).map(api_srp => {
            return {
                id: api_srp.id,
                character_id: api_srp.character_id,
                character_name: api_srp.character_name,
                amount: api_srp.amount,
                external_killmail_link: api_srp.external_killmail_link,
                fleet_id: api_srp.fleet_id ?? 0,
                primary_character_id: api_srp.primary_character_id,
                primary_character_name: api_srp.primary_character_name,
                ship_name: api_srp.ship_name,
                ship_type_id: api_srp.ship_type_id,
                killmail_id: api_srp.killmail_id,
                status: api_srp.status,
                is_corp_ship: api_srp.is_corp_ship,
                corporation_id: api_srp.corp_id,
                corporation_name: CORP_NAMES[api_srp.corp_id] ?? 'Unknown Corporation',
                category: api_srp.category,
                comments: api_srp.comments ?? '',
                ship_type: ship_types[api_srp.ship_type_id] ?? t('unknown_ship'),
                combat_log_id: api_srp.combat_log_id,
            } as SRPUI
        })

        return {
            fleet_id: fleet_id,
            srps: srps,
        } as FleetSRPUI
    })

    return {
        ship_types: get_unique_by_key(ship_class, 'type').map(i => i.type).sort(),
        fleets_srps: fleets_srps.sort((a, b) => a.fleet_id - b.fleet_id)
    }
}

export async function fetch_fleet_srps(access_token:string, fleet_id?: number, status:SRPStatus = 'pending') {
    const api_corporations = await get_all_corporations('alliance')
    const CORP_NAMES = {}
    api_corporations.map(api_corporation => CORP_NAMES[api_corporation.corporation_id] = api_corporation.corporation_name)

    return (await get_fleet_srp(access_token, { fleet_id: fleet_id, status: status}))
    .filter(api_srp => fleet_id === undefined ? api_srp.fleet_id === null : api_srp.fleet_id === fleet_id)
    .map(api_srp => {
        return {
            id: api_srp.id,
            character_id: api_srp.character_id,
            character_name: api_srp.character_name,
            amount: api_srp.amount,
            external_killmail_link: api_srp.external_killmail_link,
            fleet_id: api_srp.fleet_id,
            primary_character_id: api_srp.primary_character_id,
            primary_character_name: api_srp.primary_character_name,
            ship_name: api_srp.ship_name,
            ship_type_id: api_srp.ship_type_id,
            killmail_id: api_srp.killmail_id,
            status: api_srp.status,
            is_corp_ship: api_srp.is_corp_ship,
            corporation_id: api_srp.corp_id,
            corporation_name: CORP_NAMES[api_srp.corp_id] ?? 'Unknown Corporation',
            category: api_srp.category,
            comments: api_srp.comments ?? '',
            combat_log_id: api_srp.combat_log_id,
        } as SRPUI
    })
}

export function get_frontend_program(eve_group_name:string) {
    const FRONTEND_PROGRAMS = {
        'Dreadnought': 'dreads',
        'Force Auxiliary': 'carriers',
        'Carrier': 'carriers',
    }

    return (FRONTEND_PROGRAMS[eve_group_name] ?? 'subcapitals') as SRPFrontendPrograms
}

export async function analyze_killmail(access_token:string, external_killmail_link:string) {
    const killmail_resolve = await resolve_killmail(access_token, external_killmail_link)
    const api_programs = await get_srp_programs(access_token)

    const api_program = api_programs.find(api_program => api_program.eve_type.id === killmail_resolve.ship_type_id)
    const frontend_program = api_program?.eve_group.name ? get_frontend_program(api_program?.eve_group.name) : null

    return {
        ship_id: killmail_resolve.ship_type_id,
        ship_name: killmail_resolve.ship_name,
        character_id: killmail_resolve.victim_character_id,
        character_name: killmail_resolve.victim_character_name,
        killmail_time: killmail_resolve.killmail_time,
        value: api_program?.current_amount.srp_value ?? 0,
        program: frontend_program,
        candidate_fleets: killmail_resolve?.candidate_fleets ?? [],
    } as KillmailAnalysis
}
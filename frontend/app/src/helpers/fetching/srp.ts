import { useTranslations } from '@i18n/utils';
const t = useTranslations('en');

import type { SRPUI, FleetSRPUI } from '@dtypes/layout_components'
import { get_all_corporations } from '@helpers/api.minmatar.org/corporations'
import type { SRP, SRPStatus } from '@dtypes/api.minmatar.org'
import { get_fleet_srp } from '@helpers/api.minmatar.org/srp'
import { unique_values } from '@helpers/array'

export async function fetch_srps(access_token:string, status:SRPStatus = 'pending') {
    let api_fleet_srps:SRP[]

    const api_corporations = await get_all_corporations('alliance')
    const CORP_NAMES = {}
    api_corporations.map(api_corporation => CORP_NAMES[api_corporation.corporation_id] = api_corporation.corporation_name)

    api_fleet_srps = await get_fleet_srp(access_token, { status: status})
    const fleet_ids = unique_values(api_fleet_srps.map(srp => srp.fleet_id))
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
            } as SRPUI
        })

        return {
            fleet_id: fleet_id,
            srps: srps,
        } as FleetSRPUI
    })

    return fleets_srps.sort((a, b) => a.fleet_id - b.fleet_id)
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
        } as SRPUI
    })
}
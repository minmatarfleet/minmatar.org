import type { FleetCompositionEntry, FleetRefit, FleetShipVolunteer, FleetSupply, FleetSupplyEntry } from '@helpers/api.minmatar.org/fleets'
import { volunteer_matches_entry, get_fleet_supply } from '@helpers/api.minmatar.org/fleets'

export const EMPTY_SUPPLY:FleetSupply = { entries: [] }

/** Fetch contract + market availability for the fleet's ships. Never throws. */
export async function fetch_fleet_supply(access_token:string, fleet_id:number):Promise<FleetSupply> {
    try {
        return await get_fleet_supply(access_token, fleet_id)
    } catch (error) {
        console.error('Error fetching fleet supply:', error)
        return EMPTY_SUPPLY
    }
}

export function supply_for(entry:FleetCompositionEntry, supply:FleetSupply):FleetSupplyEntry | null {
    return supply.entries.find(row => row.key === entry.key) ?? null
}

export function refits_for(entry:FleetCompositionEntry, refits:FleetRefit[]):FleetRefit[] {
    return refits.filter(refit => entry.fitting_id ? refit.fitting_id === entry.fitting_id : refit.fleet_fitting_id === entry.fleet_fitting_id)
}

export function volunteers_for(entry:FleetCompositionEntry, volunteers:FleetShipVolunteer[]):FleetShipVolunteer[] {
    return volunteers.filter(volunteer => volunteer_matches_entry(volunteer, entry))
}

export const ship_row_id = (entry:FleetCompositionEntry) => `fleet-ship-${entry.key.replace(':', '-')}`

const CAPITAL_SHIP_GROUPS = new Set([
    'Capital',
    'Dreadnought',
    'Lancer Dreadnought',
    'Carrier',
    'Force Auxiliary',
    'Super Capital',
    'Super Carrier',
    'Supercarrier',
    'Titan',
    'Capital Industrial Ship',
    'Freighter',
    'Jump Freighter',
    'Jump Freighters',
])

export const is_capital_entry = (entry:FleetCompositionEntry) => CAPITAL_SHIP_GROUPS.has(entry.ship_group ?? '')

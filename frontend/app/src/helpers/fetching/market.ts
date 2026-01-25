import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import { get_market_contracts } from '@helpers/api.minmatar.org/market'
import { get_fittings } from '@helpers/api.minmatar.org/ships'
import type { TradeHub, MarketShipGroup, ContractUI } from '@dtypes/layout_components'
import { get_ship_info } from '@helpers/sde/ships'
import { get_market_locations } from '@helpers/api.minmatar.org/locations'
import { get_doctrines } from '@helpers/api.minmatar.org/doctrines'
import { get_fitting_item } from '@helpers/fetching/ships'
import type { Location, Doctrine, Contract } from '@dtypes/api.minmatar.org'

const CAPSULE_TYPE_ID = 670

export interface FittingMarketData {
    fitting_id: number
    fitting_name: string
    ship_id: number
    ship_name: string
    role: 'primary' | 'secondary' | 'support'
    expectation_quantity: number | null
    current_quantity: number
}

export interface DoctrineMarketData {
    doctrine_id: number
    doctrine_name: string
    fittings: FittingMarketData[]
}

export interface LocationMarketData {
    location_id: number
    location_name: string
    solar_system_name: string
    short_name: string
    doctrines: DoctrineMarketData[]
}

export async function fetch_market_contracts() {
    const trade_hubs = {}
    
    const api_fittings = await get_fittings()
    const api_contracts = await get_market_contracts()

    await Promise.all(api_contracts.map(async api_contract => {
        if (!(api_contract.location_name in trade_hubs)) {
            trade_hubs[api_contract.location_name] = {
                name: api_contract.location_name,
                contract_groups: [],
            } as TradeHub
        }

        const fitting = api_fittings.find(api_fitting => api_fitting.name === api_contract.title)
        const ship_info = fitting?.ship_id ? await get_ship_info(fitting?.ship_id) : null
        const ship_type = ship_info?.type ?? t('unknown')

        if (!(ship_type in trade_hubs[api_contract.location_name].contract_groups)) {
            trade_hubs[api_contract.location_name].contract_groups[ship_type] = {
                ship_type: ship_type,
                contracts: [],
            } as MarketShipGroup
        }

        trade_hubs[api_contract.location_name].contract_groups[ship_type].contracts.push({
            expectation_id: api_contract.expectation_id,
            title: api_contract.title,
            eve_type_id: fitting !== undefined ? fitting.ship_id : CAPSULE_TYPE_ID,
            ship_type: ship_type,
            fitting_id: api_contract.fitting_id,
            eft_format: fitting?.eft_format,
            trend_x_axis: api_contract.historical_quantity.map(point => point.date),
            trend_y_axis: api_contract.historical_quantity.map(point => point.quantity),
            current_quantity: api_contract.current_quantity,
            desired_quantity: api_contract.desired_quantity,
            responsabilities: api_contract.responsibilities,
            entities: api_contract.responsibilities.length,
        } as ContractUI)
    }))

    const trade_hubs_array:TradeHub[] = []
    for (let location_name in trade_hubs) {
        let contract_groups:MarketShipGroup[] = []

        for (let ship_type in trade_hubs[location_name].contract_groups) {
            contract_groups.push({
                ship_type: ship_type,
                contracts: trade_hubs[location_name].contract_groups[ship_type].contracts,
            } as MarketShipGroup)
        }

        trade_hubs_array.push({
            name: location_name,
            contract_groups: contract_groups
        })
    }

    return trade_hubs_array
}

export async function fetch_market_locations_with_doctrines(): Promise<LocationMarketData[]> {
    // Fetch all required data
    const [locations, doctrines, contracts] = await Promise.all([
        get_market_locations(), // Only market-active locations
        get_doctrines(),
        get_market_contracts()
    ])

    // Create a map of contracts by location_id and fitting_id for quick lookup
    const contractMap = new Map<string, Contract>()
    contracts.forEach(contract => {
        // Find the location_id for this contract's location_name
        const location = locations.find(loc => loc.location_name === contract.location_name)
        if (location) {
            const key = `${location.location_id}-${contract.fitting_id}`
            contractMap.set(key, contract)
        }
    })

    // Organize data by location
    const locationData: LocationMarketData[] = []

    for (const location of locations) {
        // Get doctrines that use this location
        const locationDoctrines = doctrines.filter(doctrine => 
            doctrine.location_ids.includes(location.location_id)
        )

        const doctrineData: DoctrineMarketData[] = []

        for (const doctrine of locationDoctrines) {
            // Combine all fittings from the doctrine (excluding secondary)
            const allFittings = [
                ...doctrine.primary_fittings.map(f => ({ ...f, role: 'primary' as const })),
                ...doctrine.support_fittings.map(f => ({ ...f, role: 'support' as const }))
            ]

            const fittingData: FittingMarketData[] = await Promise.all(allFittings.map(async fitting => {
                const contractKey = `${location.location_id}-${fitting.id}`
                const contract = contractMap.get(contractKey)

                // Get full fitting item to get ship_name
                const fittingItem = await get_fitting_item(fitting)

                return {
                    fitting_id: fitting.id,
                    fitting_name: fitting.name,
                    ship_id: fitting.ship_id,
                    ship_name: fittingItem.ship_name,
                    role: fitting.role,
                    expectation_quantity: contract ? contract.desired_quantity : null,
                    current_quantity: contract ? contract.current_quantity : 0
                }
            }))

            if (fittingData.length > 0) {
                doctrineData.push({
                    doctrine_id: doctrine.id,
                    doctrine_name: doctrine.name,
                    fittings: fittingData
                })
            }
        }

        if (doctrineData.length > 0) {
            locationData.push({
                location_id: location.location_id,
                location_name: location.location_name,
                solar_system_name: location.solar_system_name,
                short_name: location.short_name,
                doctrines: doctrineData
            })
        }
    }

    return locationData
}
import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import { get_market_contracts, get_market_locations_with_doctrines, get_market_expectations_by_location, type LocationExpectations } from '@helpers/api.minmatar.org/market'
import { get_fittings } from '@helpers/api.minmatar.org/ships'
import type { TradeHub, MarketShipGroup, ContractUI } from '@dtypes/layout_components'
import { get_ship_info } from '@helpers/sde/ships'
import { get_market_locations } from '@helpers/api.minmatar.org/locations'
import { get_doctrines } from '@helpers/api.minmatar.org/doctrines'
import { get_fitting_item } from '@helpers/fetching/ships'
import type { Fitting } from '@dtypes/api.minmatar.org'

const CAPSULE_TYPE_ID = 670

export interface FittingMarketData {
    fitting_id:             number;
    fitting_name:           string
    ship_id:                number;
    ship_name:              string;
    role:                   'primary' | 'secondary' | 'support';
    expectation_quantity:   number | null;
    current_quantity:       number;
    doctrine_name?:         string;
    eft?:                   string;
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
    // Fetch all required data using new endpoints
    const [locations, doctrines, fittings, expectations, contracts] = await Promise.all([
        get_market_locations(), // Only market-active locations
        get_doctrines(), // Need doctrines to know which fittings belong to which doctrines
        get_market_locations_with_doctrines(), // New endpoint: flat list of fittings
        get_market_expectations_by_location(), // New endpoint: expectations grouped by location
        get_market_contracts() // For current_quantity
    ])

    // Create a map of expectations by location_id and fitting_id for quick lookup
    const expectationMap = new Map<string, { quantity: number, expectation_id: number }>()
    expectations.forEach(locationExpectations => {
        locationExpectations.expectations.forEach(expectation => {
            const key = `${locationExpectations.location_id}-${expectation.fitting_id}`
            expectationMap.set(key, {
                quantity: expectation.quantity,
                expectation_id: expectation.expectation_id
            })
        })
    })

    // Create a map of current quantities by location_name and fitting_id
    const currentQuantityMap = new Map<string, number>()
    contracts.forEach(contract => {
        const key = `${contract.location_name}-${contract.fitting_id}`
        currentQuantityMap.set(key, contract.current_quantity)
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
            // Find fittings that belong to this doctrine from the new endpoint
            // The new endpoint returns fittings from doctrines, so we match by doctrine's fittings
            const doctrineFittings = fittings.filter(fitting => {
                // Check if this fitting is in the doctrine's primary or support fittings (excluding secondary)
                const isPrimary = doctrine.primary_fittings.some(f => f.id === fitting.fitting_id)
                const isSupport = doctrine.support_fittings.some(f => f.id === fitting.fitting_id)
                return isPrimary || isSupport
            })

            const doctrine_fittings:Fitting[] = [ ...doctrine.primary_fittings, ...doctrine.support_fittings ]

            const fittingData: FittingMarketData[] = await Promise.all(doctrineFittings.map(async fitting => {
                const expectationKey = `${location.location_id}-${fitting.fitting_id}`
                const expectation = expectationMap.get(expectationKey)
                
                // Get current quantity from contracts
                const currentQuantityKey = `${location.location_name}-${fitting.fitting_id}`
                const currentQuantity = currentQuantityMap.get(currentQuantityKey) || 0

                // Get full fitting from doctrine to get ship_id
                const fullFitting = doctrine.primary_fittings.find(f => f.id === fitting.fitting_id) ||
                                  doctrine.support_fittings.find(f => f.id === fitting.fitting_id)

                const fittingItem = fullFitting ? await get_fitting_item(fullFitting) : null

                return {
                    fitting_id: fitting.fitting_id,
                    fitting_name: fitting.fitting_name,
                    ship_id: fullFitting?.ship_id || 0,
                    ship_name: fittingItem?.ship_name || '',
                    role: fitting.role as 'primary' | 'support',
                    expectation_quantity: expectation ? expectation.quantity : null,
                    current_quantity: currentQuantity,
                    eft: doctrine_fittings.find(doctrine_fitting => doctrine_fitting.id === fitting.fitting_id)?.eft_format
                } as FittingMarketData
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
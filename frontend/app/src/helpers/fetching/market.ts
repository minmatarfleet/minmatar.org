import { useTranslations } from '@i18n/utils';

const t = useTranslations('en');

import { get_market_contracts, get_market_locations_with_doctrines, get_market_expectations_by_location } from '@helpers/api.minmatar.org/market'
import { get_market_locations } from '@helpers/api.minmatar.org/locations'
import { get_doctrines } from '@helpers/api.minmatar.org/doctrines'
import { get_fitting_item } from '@helpers/fetching/ships'
import type {
    Fitting,
    FittingMarketData,
    DoctrineMarketData,
    LocationMarketData,
} from '@dtypes/api.minmatar.org'

export async function fetch_market_locations_with_doctrines(): Promise<LocationMarketData[]> {
    // Fetch all required data using new endpoints
    const [locations, doctrines, fittings, expectations] = await Promise.all([
        get_market_locations(), // Only market-active locations
        get_doctrines(), // Need doctrines to know which fittings belong to which doctrines
        get_market_locations_with_doctrines(), // New endpoint: flat list of fittings
        get_market_expectations_by_location(), // New endpoint: expectations grouped by location
    ])

    // Fetch contracts per location (API returns all contracts for a given location_id)
    const contractsByLocation = await Promise.all(
        locations.map(loc => get_market_contracts(loc.location_id))
    )

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
    contractsByLocation.forEach((contracts, i) => {
        const location = locations[i]
        contracts.forEach(contract => {
            currentQuantityMap.set(`${location.location_name}-${contract.fitting_id}`, contract.current_quantity)
        })
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
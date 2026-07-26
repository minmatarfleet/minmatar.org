import type { Location } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/eveonline/locations`

/** Dedupes concurrent fetches in one render; must not outlive the request (SSR). */
let locations_inflight: Promise<Location[]> | null = null

/**
 * Fetch all locations from the API.
 * Concurrent callers share one in-flight request; each page load refetches.
 */
export async function get_locations(): Promise<Location[]> {
    if (locations_inflight)
        return locations_inflight

    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/`

    console.log(`Requesting: ${ENDPOINT}`)

    locations_inflight = (async () => {
        try {
            const response = await fetch(ENDPOINT, {
                headers: headers
            })

            if (!response.ok) {
                throw new Error(get_error_message(
                    response.status,
                    `GET ${ENDPOINT}`
                ), {
                    cause: response.status
                });
            }

            return await response.json() as Location[]
        } catch (error) {
            throw new Error(`Error fetching locations: ${error.message}`, { cause: error.cause });
        } finally {
            locations_inflight = null
        }
    })()

    return locations_inflight
}

/**
 * Get locations by their IDs. Filters the full locations list client-side.
 * @param location_ids Array of location IDs to filter by
 * @returns Filtered array of locations matching the provided IDs
 */
export async function get_locations_by_ids(location_ids: number[]): Promise<Location[]> {
    const all_locations = await get_locations()
    const ids_set = new Set(location_ids)
    return all_locations.filter(location => ids_set.has(location.location_id))
}

/**
 * Get locations filtered by market_active flag.
 * @returns Array of locations where market_active is true
 */
export async function get_market_locations(): Promise<Location[]> {
    const all_locations = await get_locations()
    return all_locations.filter(location => location.market_active)
}

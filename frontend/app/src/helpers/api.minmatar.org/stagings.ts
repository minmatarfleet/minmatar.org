import type { Stagings } from '@dtypes/api.minmatar.org'
import { api_request, type ApiToken } from '@helpers/api.minmatar.org/client'

const ENDPOINT = `${import.meta.env.API_URL}/api/structures/locations/stagings`

/** What a page shows when there is nothing to show: no home, no deployment. */
const NO_STAGINGS: Stagings = { home: null, deployments: [] }

/**
 * The home staging and the deployment locations this pilot may see.
 * Never throws: a failed request reads as "no deployment", so the pages that
 * show the strip or the doctrine tabs look exactly as they did before.
 */
export async function get_stagings(token?: ApiToken): Promise<Stagings> {
    try {
        const stagings = await api_request<Stagings>(ENDPOINT, { token })
        return stagings ?? NO_STAGINGS
    } catch (error) {
        console.error('Error fetching stagings:', error)
        return NO_STAGINGS
    }
}

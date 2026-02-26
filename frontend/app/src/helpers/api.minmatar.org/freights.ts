import type { FreightRoute, RouteCost, FreightContract, SpaceTruckerStatistics } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/freight`

export async function get_routes() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/routes`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as FreightRoute[];
    } catch (error) {
        throw new Error(`Error fetching freight routes: ${error.message}`);
    }
}

export async function get_route_cost(route_id: number, m3: number, collateral: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const params = new URLSearchParams({ m3: String(m3), collateral: String(collateral) })
    const ENDPOINT = `${API_ENDPOINT}/routes/${route_id}/cost?${params}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as RouteCost;
    } catch (error) {
        throw new Error(`Error fetching freight route cost: ${error.message}`);
    }
}

export async function get_contracts(history:boolean = false) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/contracts${history ? '/history' : ''}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as FreightContract[];
    } catch (error) {
        throw new Error(`Error fetching freight contracts: ${error.message}`);
    }
}

export async function get_characters_statistics() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/character-statistics`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as SpaceTruckerStatistics[];
    } catch (error) {
        throw new Error(`Error fetching freight contracts: ${error.message}`);
    }
}
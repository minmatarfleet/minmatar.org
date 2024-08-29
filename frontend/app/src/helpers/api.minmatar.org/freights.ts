import type { FreightRoute, RouteOptions, RouteCost } from '@dtypes/api.minmatar.org'
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

export async function get_route_options(route_id: number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/${route_id}/options`

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

        return await response.json() as RouteOptions[];
    } catch (error) {
        throw new Error(`Error fetching freight routes options: ${error.message}`);
    }
}

export async function get_route_cost(route_id: number, route_option_id: number, collateral:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/routes/${route_id}/options/${route_option_id ?? route_id}/cost?collateral=${collateral}`

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

        return await response.json() as RouteCost;
    } catch (error) {
        throw new Error(`Error fetching freight route cost: ${error.message}`);
    }
}
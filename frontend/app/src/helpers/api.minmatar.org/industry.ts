import type { BaseIndustryOrder, NestedIndustryOrder } from '@dtypes/api.minmatar.org'
import { get_error_message, parse_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/industry`

export async function get_orders_summary_nested() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/summary/nested`

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
            ))
        }

        return await response.json() as { roots: NestedIndustryOrder[] };
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`);
    }
}

export async function get_orders_summary_flat() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/summary/flat`

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
            ))
        }

        return await response.json() as { items: BaseIndustryOrder[] };
    } catch (error) {
        throw new Error(`Error fetching contracts: ${error.message}`);
    }
}
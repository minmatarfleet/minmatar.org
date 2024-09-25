import type { SystemMoon, MoonSummarySystem } from '@dtypes/api.minmatar.org'
import { get_error_message, query_string } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/moons`

export async function get_system_moons(access_token:string, system:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}?${query_string({'system': system})}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as SystemMoon[];
    } catch (error) {
        throw new Error(`Error fetching system moons: ${error.message}`);
    }
}

export async function get_moon_summary(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/summary`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as MoonSummarySystem[];
    } catch (error) {
        throw new Error(`Error fetching moon summary: ${error.message}`);
    }
}

export async function add_moon(access_token:string, paste:string) {
    const data = JSON.stringify({
        paste: paste
    })

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${import.meta.env.API_URL}/api/moon_paste`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: data,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as number[];
    } catch (error) {
        throw new Error(`Error adding moon: ${error.message}`);
    }
}
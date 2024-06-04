import type { Corporation, CorporationType, CorporationInfo } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/corporations`

export async function get_all_corporations(corporation_type:CorporationType) {
    const headers = {
        'Content-Type': 'application/json'
    }

    const ENDPOINT = `${API_ENDPOINT}/corporations?corporation_type=${corporation_type}`

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

        return await response.json() as Corporation[];
    } catch (error) {
        throw new Error(`Error fetching corporations: ${error.message}`);
    }
}

export async function get_corporation_by_id(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/corporations/${id}`

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

        return await response.json() as Corporation;
    } catch (error) {
        throw new Error(`Error fetching corporation: ${error.message}`);
    }
}

export async function get_corporation_info(id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/corporations/${id}/info`

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

        return await response.json() as CorporationInfo;
    } catch (error) {
        throw new Error(`Error fetching corporation: ${error.message}`);
    }
}
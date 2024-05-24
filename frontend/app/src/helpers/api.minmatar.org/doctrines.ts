import type { Doctrine } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/doctrines`

export async function get_doctrines() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = API_ENDPOINT

    console.log(`Requesting: ${ENDPOINT}/`)

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

        return await response.json() as Doctrine[];
    } catch (error) {
        throw new Error(`Error fetching sigs: ${error.message}`);
    }
}

export async function get_doctrine_by_id(id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}`

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

        return await response.json() as Doctrine;
    } catch (error) {
        throw new Error(`Error fetching sigs: ${error.message}`);
    }
}
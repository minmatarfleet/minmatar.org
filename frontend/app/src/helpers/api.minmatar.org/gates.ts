import type { UserGates } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/users/me/gates`

export async function get_user_gates(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}`)

    try {
        const response = await fetch(API_ENDPOINT, {
            headers: headers
        })

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${API_ENDPOINT}`
            ), {
                cause: response.status
            })
        }

        return await response.json() as UserGates;
    } catch (error) {
        throw new Error(`Error fetching user gates: ${error.message}`, { cause: error.cause });
    }
}

import type { Player, PrimeTime } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/eveonline/players`

export async function get_current_player(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/current`

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

        return await response.json() as Player;
    } catch (error) {
        throw new Error(`Error fetching current player: ${error.message}`);
    }
}

export async function update_prime_time(access_token:string, prime_time:PrimeTime, nickname:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/current`
    const METHOD = 'PATCH'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: METHOD,
            headers: headers,
            body: JSON.stringify({ nickname: nickname, prime_time: prime_time }),
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `${METHOD} ${ENDPOINT}`
            ))
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error setting prime time: ${error.message}`);
    }
}
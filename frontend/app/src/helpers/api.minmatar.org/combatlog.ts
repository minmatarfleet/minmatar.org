import type { CombatLog } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/combatlog/`

export async function analize_log(combatlog:string) {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = API_ENDPOINT

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: combatlog,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as CombatLog;
    } catch (error) {
        throw new Error(`Error creating fleet: ${error.message}`);
    }
}
import type { StructureTimer, StructureTimerRequest, VerifyStructureTimerRequest } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/structures/`

export async function get_structure_timers(access_token:string, active:boolean = true) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}timers?active=${JSON.stringify(active)}`

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

        return await response.json() as StructureTimer[];
    } catch (error) {
        throw new Error(`Error fetching structure timers: ${error.message}`);
    }
}

export async function create_structure_timer(access_token:string, timer:StructureTimerRequest) {
    const data = JSON.stringify(timer);

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}timers`

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

        return await response.json() as StructureTimer;
    } catch (error) {
        throw new Error(`Error creating structure timer: ${error.message}`);
    }
}



export async function verify_structure_timer(access_token:string, timer_id:number, request:VerifyStructureTimerRequest) {
    const data = JSON.stringify(request);

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}timers/${timer_id}/verify`

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

        return await response.json() as StructureTimer;
    } catch (error) {
        throw new Error(`Error creating structure timer: ${error.message}`);
    }
}
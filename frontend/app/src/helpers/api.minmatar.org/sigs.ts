import type { Group, SigRequest } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/sigs`

export async function get_groups() {
    const headers = {
        'Content-Type': 'application/json',
    }

    const ENDPOINT = API_ENDPOINT

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

        return await response.json() as Group[];
    } catch (error) {
        throw new Error(`Error fetching sigs: ${error.message}`);
    }
}

export async function get_current_groups(access_token:string) {
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

        return await response.json() as Group[];
    } catch (error) {
        throw new Error(`Error fetching current sigs: ${error.message}`);
    }
}

export async function get_group_by_id(id:number) {
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
            ))
        }

        return await response.json() as Group
    } catch (error) {
        throw new Error(`Error fetching sig by id: ${error.message}`)
    }
}

export async function get_group_requests(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}/requests`

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

        return await response.json() as SigRequest[]
    } catch (error) {
        throw new Error(`Error fetching group requests: ${error.message}`)
    }
}

export async function create_group_request(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}/requests`

    console.log(`Requesting POST: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as SigRequest
    } catch (error) {
        throw new Error(`Error creating sig request: ${error.message}`)
    }
}

export async function approve_group_request(access_token:string, id:number, request_id: number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}/requests/${request_id}/approve`

    console.log(`Requesting: POST ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as SigRequest
    } catch (error) {
        throw new Error(`Error approving sig request: ${error.message}`)
    }
}

export async function deny_group_request(access_token:string, id:number, request_id: number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}/requests/${request_id}/deny`

    console.log(`Requesting: POST ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return await response.json() as SigRequest
    } catch (error) {
        throw new Error(`Error denying sig request: ${error.message}`)
    }
}

export async function remove_group_member(access_token:string, id:number, user_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}/members/${user_id}`

    console.log(`Requesting DELETE: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'DELETE',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `DELETE ${ENDPOINT}`
            ))
        }

        return await response.json() as Group
    } catch (error) {
        throw new Error(`Error removing sig member: ${error.message}`)
    }
}
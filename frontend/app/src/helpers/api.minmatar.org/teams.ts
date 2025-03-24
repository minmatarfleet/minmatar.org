import type { Group, TeamRequest } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/teams`

export async function get_groups() {
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
            ))
        }

        return await response.json() as Group[];
    } catch (error) {
        throw new Error(`Error fetching team: ${error.message}`);
    }
}

export async function get_current_groups(access_token:string, director:boolean = false) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/current?director=${JSON.stringify(director)}`

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
        throw new Error(`Error fetching current teams: ${error.message}`);
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
        throw new Error(`Error fetching team by id: ${error.message}`)
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

        return await response.json() as TeamRequest[]
    } catch (error) {
        throw new Error(`Error fetching team requests: ${error.message}`)
    }
}

export async function create_group_request(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${id}/requests`

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

        return await response.json() as TeamRequest
    } catch (error) {
        throw new Error(`Error creating team request: ${error.message}`)
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

        return await response.json() as TeamRequest
    } catch (error) {
        throw new Error(`Error approving team request: ${error.message}`)
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

        return await response.json() as TeamRequest
    } catch (error) {
        throw new Error(`Error denying team request: ${error.message}`)
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
        throw new Error(`Error removing teams member: ${error.message}`)
    }
}